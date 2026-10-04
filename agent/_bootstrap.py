"""Bootstrap run by ``Sandbox.run_python``: guards file access, then runs the agent's code.

Invoked as ``python -c <this source> <sandbox_root> <tmp_dir> <log_fd>`` with the agent's
code on stdin. A ``sys.addaudithook`` hook blocks (raises PermissionError for) file access
outside the sandbox, process spawning and network connections, and reports each blocked
attempt on ``log_fd`` so the parent can append it to the tool output. Best effort only: it
is not an OS-level jail (e.g. ctypes can get around it).
"""

import os
import collections
import enum
import site
import sys
import sysconfig
import threading
import traceback
import types

MAX_LOGGED = 50
READ_ONLY_EXTRA = ("/dev/null", "/dev/zero", "/dev/urandom", "/dev/random", "/etc/localtime", "/etc/timezone",
                   "/usr/share/zoneinfo", "/usr/share/fonts", "/proc/self", "/proc/cpuinfo", "/proc/meminfo",
                   "/sys/devices/system/cpu", "/sys/fs/cgroup")
SPAWN_EVENTS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile", "pty.spawn")
NETWORK_EVENTS = ("socket.connect", "socket.sendto", "socket.sendmsg")
INTROSPECTION_EVENTS = ("sys._getframe", "sys._current_frames", "sys._current_exceptions",
                        "sys.settrace", "sys.setprofile", "gc.get_objects", "gc.get_referrers", "gc.get_referents")
WRITE_PATH_EVENTS = ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.utime", "os.truncate",
                     "shutil.rmtree", "os.chdir", "os.chroot")
TWO_PATH_EVENTS = ("os.rename", "os.link", "os.symlink")
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def _real(path) -> str:
    return os.path.realpath(os.path.join(os.getcwd(), os.fsdecode(path)))


def _under(path: str, dirs) -> bool:
    return any(path == d or path.startswith(d.rstrip(os.sep) + os.sep) for d in dirs)


def main() -> None:
    root, tmp, log_fd = os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2]), int(sys.argv[3])
    code = sys.stdin.read()
    sys.argv = ["-"]

    rw_dirs = (root, tmp)
    lib_dirs = {p for k, p in sysconfig.get_paths().items() if k in ("stdlib", "platstdlib", "purelib", "platlib")}
    lib_dirs.update(getattr(site, "getsitepackages", list)())
    if site.ENABLE_USER_SITE:
        lib_dirs.add(site.getusersitepackages())
    lib_dirs = {os.path.realpath(p) for p in lib_dirs}
    read_dirs = rw_dirs + tuple(sorted(lib_dirs)) + READ_ONLY_EXTRA

    # Drop import paths and editable-install finders that point outside the sandbox / Python install
    # (e.g. the harness repo), so harness packages are simply not importable.
    sys.path[:] = [p for p in sys.path if "__editable__" not in p and (p == "" or _under(_real(p), read_dirs))]
    sys.path_importer_cache.clear()
    sys.meta_path[:] = [f for f in sys.meta_path if "__editable__" not in getattr(f, "__module__", "")]

    state = threading.local()
    logged = [0]
    trusted_frame_callers = {collections.namedtuple.__code__, enum.EnumType._create_.__code__}

    def block(desc: str, reason: str = "access outside the sandbox is not allowed"):
        try:
            if logged[0] < MAX_LOGGED:
                os.write(log_fd, (desc[:300].replace("\n", " ") + "\n").encode("utf-8", "replace"))
            elif logged[0] == MAX_LOGGED:
                os.write(log_fd, b"... (further blocked operations not logged)\n")
        except OSError:
            pass
        logged[0] += 1
        return PermissionError(f"[sandbox] blocked {desc}: {reason}")

    def check(event: str, args):
        if event == "sys._getframe" and sys._getframe(2).f_code in trusted_frame_callers:
            return None
        if event in INTROSPECTION_EVENTS or (event == "object.__getattr__" and args[1] in ("tb_frame", "f_code")):
            return block(event, "runtime frame inspection is not allowed")
        if event == "open":
            path, mode, flags = (tuple(args) + (None, None, None))[:3]
            if path is None or isinstance(path, int):
                return None
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                mode is None and isinstance(flags, int) and bool(flags & WRITE_FLAGS))
            real = _real(path)
            if not _under(real, rw_dirs if writing else read_dirs):
                return block(f"open({os.fsdecode(path)!r}, {mode or ('w' if writing else 'r')!r})")
        elif event in ("os.listdir", "os.scandir"):
            path = args[0] if args else None
            if isinstance(path, int):
                return None
            if not _under(_real("." if path is None else path), read_dirs):
                return block(f"{event}({os.fsdecode(path)!r})")
        elif event in WRITE_PATH_EVENTS:
            path = args[0] if args else None
            if path is not None and not isinstance(path, int) and not _under(_real(path), rw_dirs):
                return block(f"{event}({os.fsdecode(path)!r})")
        elif event in TWO_PATH_EVENTS:
            paths = [p for p in args[:2] if p is not None and not isinstance(p, int)]
            if event == "os.symlink":
                paths = paths[1:]  # the link location must be inside; following it is checked on open
            if any(not _under(_real(p), rw_dirs) for p in paths):
                return block(f"{event}({', '.join(repr(os.fsdecode(p)) for p in args[:2])})")
        elif event in SPAWN_EVENTS:
            return block(event, "starting other processes is not allowed")
        elif event in NETWORK_EVENTS:
            return block(f"{event}({args[1]!r})" if len(args) > 1 else event, "network access is not allowed")
        elif event == "ctypes.dlopen":
            name = args[0] if args else None
            if name is not None and os.sep in os.fsdecode(name) and not _under(_real(name), read_dirs):
                return block(f"ctypes.dlopen({os.fsdecode(name)!r})")
        return None

    def hook(event: str, args) -> None:
        if getattr(state, "busy", False):
            return
        state.busy = True
        try:
            err = check(event, args)
        except Exception:
            err = PermissionError(f"[sandbox] guard could not validate {event}")
        finally:
            state.busy = False
        if err is not None:
            raise err

    try:
        compiled = compile(code, "<stdin>", "exec")
    except SyntaxError as exc:
        traceback.print_exception(type(exc), exc, None)
        sys.exit(1)
    agent_module = types.ModuleType("__main__")
    namespace = agent_module.__dict__
    namespace.update(__file__="<stdin>", __builtins__=__builtins__)
    sys.modules["__main__"] = agent_module
    sys.addaudithook(hook)
    try:
        exec(compiled, namespace)
    except SystemExit:
        raise
    except BaseException as exc:
        tb = exc.__traceback__.tb_next if exc.__traceback__ is not None else None
        frames = []
        state.busy = True
        try:
            while tb is not None:
                frame_code = tb.tb_frame.f_code
                frames.append((frame_code.co_filename, tb.tb_lineno, frame_code.co_name))
                tb = tb.tb_next
        finally:
            state.busy = False
        if frames:
            print("Traceback (most recent call last):", file=sys.stderr)
            for filename, line, name in frames:
                print(f'  File "{filename}", line {line}, in {name}', file=sys.stderr)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.stdout.flush()
        sys.exit(1)


main()
