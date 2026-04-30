import os
import typing
import typing_extensions

def _log_throughput(op: str, size_bytes: int, dur_s: float) -> None: ...

class _SandboxFilesystem:
    """mdmd:namespace
    Namespace for Sandbox filesystem APIs.
    """
    def __init__(self, sandbox):
        """mdmd:hidden"""
        ...

    async def read_bytes(self, remote_path: str) -> bytes:
        """Read a file from the Sandbox and return its contents as bytes.

        `remote_path` must be an absolute path to a file in the Sandbox.

        **Raises**

        - `SandboxFilesystemNotFoundError`: the path does not exist.
        - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
        - `SandboxFilesystemPermissionError`: read permission is denied.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
        contents = sandbox.filesystem.read_bytes("/tmp/hello.bin")
        print(contents.decode("utf-8"))
        ```
        """
        ...

    async def read_text(self, remote_path: str) -> str:
        """Read a file from the Sandbox and return its contents as a UTF-8 string.

        `remote_path` must be an absolute path to a file in the Sandbox.

        **Raises**

        - `SandboxFilesystemNotFoundError`: the path does not exist.
        - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
        - `SandboxFilesystemPermissionError`: read permission is denied.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
        contents = sandbox.filesystem.read_text("/tmp/hello.txt")
        print(contents)
        ```
        """
        ...

    async def copy_to_local(self, remote_path: str, local_path: typing.Union[str, os.PathLike]) -> None:
        """Copy a file from the Sandbox to a local path.

        `remote_path` must be an absolute path to a file in the Sandbox.
        Parent directories for `local_path` are created if needed.
        The local file is overwritten if it already exists.

        **Raises**

        - `SandboxFilesystemNotFoundError`: the remote path does not exist.
        - `SandboxFilesystemIsADirectoryError`: the remote path points to a directory.
        - `SandboxFilesystemPermissionError`: read permission is denied in the Sandbox.
        - `SandboxFilesystemError`: the command fails for any other reason.
        - `IsADirectoryError`: `local_path` points to a directory.
        - `NotADirectoryError`: a component of the `local_path` parent is not a directory.
        - `PermissionError`: writing `local_path` is not permitted.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
        sandbox.filesystem.copy_to_local("/tmp/hello.txt", "/tmp/local-hello.txt")
        ```
        """
        ...

    async def write_bytes(self, data: typing.Union[bytes, bytearray, memoryview], remote_path: str) -> None:
        """Write binary content to a file in the Sandbox.

        `remote_path` must be an absolute path to a file in the Sandbox.
        Parent directories for `remote_path` are created if needed.
        The remote file is overwritten if it already exists.

        **Raises**

        - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
        - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
        - `SandboxFilesystemPermissionError`: write permission is denied.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
        ```
        """
        ...

    async def write_text(self, data: str, remote_path: str) -> None:
        """Write UTF-8 text to a file in the Sandbox.

        `remote_path` must be an absolute path to a file in the Sandbox.
        Parent directories for `remote_path` are created if needed.
        The remote file is overwritten if it already exists.

        **Raises**

        - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
        - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
        - `SandboxFilesystemPermissionError`: write permission is denied.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
        ```
        """
        ...

    async def copy_from_local(self, local_path: typing.Union[str, os.PathLike], remote_path: str) -> None:
        """Copy a local file into the Sandbox.

        `remote_path` must be an absolute path to a file in the Sandbox.
        Parent directories for `remote_path` are created if needed.
        The remote file is overwritten if it already exists.

        **Raises**

        - `SandboxFilesystemNotADirectoryError`: a parent path component of `remote_path` is not a directory.
        - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
        - `SandboxFilesystemPermissionError`: write permission is denied in the Sandbox.
        - `SandboxFilesystemError`: the command fails for any other reason.
        - `FileNotFoundError`: `local_path` does not exist.
        - `IsADirectoryError`: `local_path` is a directory.
        - `PermissionError`: reading `local_path` is not permitted.

        **Usage**

        ```python fixture:sandbox
        import tempfile
        from pathlib import Path

        local_path = Path(tempfile.mktemp())
        local_path.write_text("Hello, world!\n")
        sandbox.filesystem.copy_from_local(local_path, "/tmp/hello.txt")
        ```
        """
        ...

    async def remove(self, remote_path: str, *, recursive: bool = False) -> None:
        """Remove a file or directory in the Sandbox.

        `remote_path` must be an absolute path in the Sandbox.

        When `remote_path` is a directory and `recursive` is `False` (the
        default), removes it only if it is empty. When `recursive` is `True`,
        removes the directory and all its contents.

        Recursive directory removal is not supported on all mounts.
        In particular, `CloudBucketMount` does not support it. An
        `InvalidError` is raised in that case.

        **Raises**

        - `SandboxFilesystemNotFoundError`: the path does not exist.
        - `SandboxFilesystemDirectoryNotEmptyError`: `recursive` is `False` and the directory is not empty.
        - `SandboxFilesystemPermissionError`: removal is not permitted.
        - `InvalidError`: the operation is not supported by the mount.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        To remove a file:

        ```python fixture:sandbox
        sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
        sandbox.filesystem.remove("/tmp/hello.bin")
        ```

        To remove a directory and all its contents:

        ```python fixture:sandbox
        sandbox.filesystem.make_directory("/tmp/mydir/subdir")
        sandbox.filesystem.remove("/tmp/mydir", recursive=True)
        ```
        """
        ...

    async def make_directory(self, remote_path: str, *, create_parents: bool = True) -> None:
        """Create a new directory in the Sandbox.

        `remote_path` must be an absolute path in the Sandbox.

        When `create_parents` is `True` (the default), any missing parent directories are created and the call is
        idempotent (succeeds silently if the directory already exists). When `create_parents` is `False`, the
        immediate parent directory must already exist and the path must not already exist.

        **Raises**

        - `SandboxFilesystemNotFoundError`: the parent directory does not exist and `create_parents` is `False`.
        - `SandboxFilesystemPathAlreadyExistsError`: the path already exists.
        - `SandboxFilesystemNotADirectoryError`: a path component is not a directory.
        - `SandboxFilesystemPermissionError`: creation is not permitted.
        - `InvalidError`: the operation is not supported by the mount.
        - `SandboxFilesystemError`: the command fails for any other reason.

        **Usage**

        ```python fixture:sandbox
        sandbox.filesystem.make_directory("/tmp/a/b/c")
        ```
        """
        ...

class SandboxFilesystem:
    """mdmd:namespace
    Namespace for Sandbox filesystem APIs.
    """
    def __init__(self, sandbox):
        """mdmd:hidden"""
        ...

    class __read_bytes_spec(typing_extensions.Protocol):
        def __call__(self, /, remote_path: str) -> bytes:
            """Read a file from the Sandbox and return its contents as bytes.

            `remote_path` must be an absolute path to a file in the Sandbox.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            contents = sandbox.filesystem.read_bytes("/tmp/hello.bin")
            print(contents.decode("utf-8"))
            ```
            """
            ...

        async def aio(self, /, remote_path: str) -> bytes:
            """Read a file from the Sandbox and return its contents as bytes.

            `remote_path` must be an absolute path to a file in the Sandbox.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            contents = sandbox.filesystem.read_bytes("/tmp/hello.bin")
            print(contents.decode("utf-8"))
            ```
            """
            ...

    read_bytes: __read_bytes_spec

    class __read_text_spec(typing_extensions.Protocol):
        def __call__(self, /, remote_path: str) -> str:
            """Read a file from the Sandbox and return its contents as a UTF-8 string.

            `remote_path` must be an absolute path to a file in the Sandbox.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            contents = sandbox.filesystem.read_text("/tmp/hello.txt")
            print(contents)
            ```
            """
            ...

        async def aio(self, /, remote_path: str) -> str:
            """Read a file from the Sandbox and return its contents as a UTF-8 string.

            `remote_path` must be an absolute path to a file in the Sandbox.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            contents = sandbox.filesystem.read_text("/tmp/hello.txt")
            print(contents)
            ```
            """
            ...

    read_text: __read_text_spec

    class __copy_to_local_spec(typing_extensions.Protocol):
        def __call__(self, /, remote_path: str, local_path: typing.Union[str, os.PathLike]) -> None:
            """Copy a file from the Sandbox to a local path.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `local_path` are created if needed.
            The local file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the remote path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the remote path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied in the Sandbox.
            - `SandboxFilesystemError`: the command fails for any other reason.
            - `IsADirectoryError`: `local_path` points to a directory.
            - `NotADirectoryError`: a component of the `local_path` parent is not a directory.
            - `PermissionError`: writing `local_path` is not permitted.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            sandbox.filesystem.copy_to_local("/tmp/hello.txt", "/tmp/local-hello.txt")
            ```
            """
            ...

        async def aio(self, /, remote_path: str, local_path: typing.Union[str, os.PathLike]) -> None:
            """Copy a file from the Sandbox to a local path.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `local_path` are created if needed.
            The local file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the remote path does not exist.
            - `SandboxFilesystemIsADirectoryError`: the remote path points to a directory.
            - `SandboxFilesystemPermissionError`: read permission is denied in the Sandbox.
            - `SandboxFilesystemError`: the command fails for any other reason.
            - `IsADirectoryError`: `local_path` points to a directory.
            - `NotADirectoryError`: a component of the `local_path` parent is not a directory.
            - `PermissionError`: writing `local_path` is not permitted.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            sandbox.filesystem.copy_to_local("/tmp/hello.txt", "/tmp/local-hello.txt")
            ```
            """
            ...

    copy_to_local: __copy_to_local_spec

    class __write_bytes_spec(typing_extensions.Protocol):
        def __call__(self, /, data: typing.Union[bytes, bytearray, memoryview], remote_path: str) -> None:
            """Write binary content to a file in the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            ```
            """
            ...

        async def aio(self, /, data: typing.Union[bytes, bytearray, memoryview], remote_path: str) -> None:
            """Write binary content to a file in the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            ```
            """
            ...

    write_bytes: __write_bytes_spec

    class __write_text_spec(typing_extensions.Protocol):
        def __call__(self, /, data: str, remote_path: str) -> None:
            """Write UTF-8 text to a file in the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            ```
            """
            ...

        async def aio(self, /, data: str, remote_path: str) -> None:
            """Write UTF-8 text to a file in the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.write_text("Hello, world!\n", "/tmp/hello.txt")
            ```
            """
            ...

    write_text: __write_text_spec

    class __copy_from_local_spec(typing_extensions.Protocol):
        def __call__(self, /, local_path: typing.Union[str, os.PathLike], remote_path: str) -> None:
            """Copy a local file into the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component of `remote_path` is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied in the Sandbox.
            - `SandboxFilesystemError`: the command fails for any other reason.
            - `FileNotFoundError`: `local_path` does not exist.
            - `IsADirectoryError`: `local_path` is a directory.
            - `PermissionError`: reading `local_path` is not permitted.

            **Usage**

            ```python fixture:sandbox
            import tempfile
            from pathlib import Path

            local_path = Path(tempfile.mktemp())
            local_path.write_text("Hello, world!\n")
            sandbox.filesystem.copy_from_local(local_path, "/tmp/hello.txt")
            ```
            """
            ...

        async def aio(self, /, local_path: typing.Union[str, os.PathLike], remote_path: str) -> None:
            """Copy a local file into the Sandbox.

            `remote_path` must be an absolute path to a file in the Sandbox.
            Parent directories for `remote_path` are created if needed.
            The remote file is overwritten if it already exists.

            **Raises**

            - `SandboxFilesystemNotADirectoryError`: a parent path component of `remote_path` is not a directory.
            - `SandboxFilesystemIsADirectoryError`: `remote_path` points to a directory.
            - `SandboxFilesystemPermissionError`: write permission is denied in the Sandbox.
            - `SandboxFilesystemError`: the command fails for any other reason.
            - `FileNotFoundError`: `local_path` does not exist.
            - `IsADirectoryError`: `local_path` is a directory.
            - `PermissionError`: reading `local_path` is not permitted.

            **Usage**

            ```python fixture:sandbox
            import tempfile
            from pathlib import Path

            local_path = Path(tempfile.mktemp())
            local_path.write_text("Hello, world!\n")
            sandbox.filesystem.copy_from_local(local_path, "/tmp/hello.txt")
            ```
            """
            ...

    copy_from_local: __copy_from_local_spec

    class __remove_spec(typing_extensions.Protocol):
        def __call__(self, /, remote_path: str, *, recursive: bool = False) -> None:
            """Remove a file or directory in the Sandbox.

            `remote_path` must be an absolute path in the Sandbox.

            When `remote_path` is a directory and `recursive` is `False` (the
            default), removes it only if it is empty. When `recursive` is `True`,
            removes the directory and all its contents.

            Recursive directory removal is not supported on all mounts.
            In particular, `CloudBucketMount` does not support it. An
            `InvalidError` is raised in that case.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemDirectoryNotEmptyError`: `recursive` is `False` and the directory is not empty.
            - `SandboxFilesystemPermissionError`: removal is not permitted.
            - `InvalidError`: the operation is not supported by the mount.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            To remove a file:

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            sandbox.filesystem.remove("/tmp/hello.bin")
            ```

            To remove a directory and all its contents:

            ```python fixture:sandbox
            sandbox.filesystem.make_directory("/tmp/mydir/subdir")
            sandbox.filesystem.remove("/tmp/mydir", recursive=True)
            ```
            """
            ...

        async def aio(self, /, remote_path: str, *, recursive: bool = False) -> None:
            """Remove a file or directory in the Sandbox.

            `remote_path` must be an absolute path in the Sandbox.

            When `remote_path` is a directory and `recursive` is `False` (the
            default), removes it only if it is empty. When `recursive` is `True`,
            removes the directory and all its contents.

            Recursive directory removal is not supported on all mounts.
            In particular, `CloudBucketMount` does not support it. An
            `InvalidError` is raised in that case.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the path does not exist.
            - `SandboxFilesystemDirectoryNotEmptyError`: `recursive` is `False` and the directory is not empty.
            - `SandboxFilesystemPermissionError`: removal is not permitted.
            - `InvalidError`: the operation is not supported by the mount.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            To remove a file:

            ```python fixture:sandbox
            sandbox.filesystem.write_bytes(b"Hello, world!\n", "/tmp/hello.bin")
            sandbox.filesystem.remove("/tmp/hello.bin")
            ```

            To remove a directory and all its contents:

            ```python fixture:sandbox
            sandbox.filesystem.make_directory("/tmp/mydir/subdir")
            sandbox.filesystem.remove("/tmp/mydir", recursive=True)
            ```
            """
            ...

    remove: __remove_spec

    class __make_directory_spec(typing_extensions.Protocol):
        def __call__(self, /, remote_path: str, *, create_parents: bool = True) -> None:
            """Create a new directory in the Sandbox.

            `remote_path` must be an absolute path in the Sandbox.

            When `create_parents` is `True` (the default), any missing parent directories are created and the call is
            idempotent (succeeds silently if the directory already exists). When `create_parents` is `False`, the
            immediate parent directory must already exist and the path must not already exist.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the parent directory does not exist and `create_parents` is `False`.
            - `SandboxFilesystemPathAlreadyExistsError`: the path already exists.
            - `SandboxFilesystemNotADirectoryError`: a path component is not a directory.
            - `SandboxFilesystemPermissionError`: creation is not permitted.
            - `InvalidError`: the operation is not supported by the mount.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.make_directory("/tmp/a/b/c")
            ```
            """
            ...

        async def aio(self, /, remote_path: str, *, create_parents: bool = True) -> None:
            """Create a new directory in the Sandbox.

            `remote_path` must be an absolute path in the Sandbox.

            When `create_parents` is `True` (the default), any missing parent directories are created and the call is
            idempotent (succeeds silently if the directory already exists). When `create_parents` is `False`, the
            immediate parent directory must already exist and the path must not already exist.

            **Raises**

            - `SandboxFilesystemNotFoundError`: the parent directory does not exist and `create_parents` is `False`.
            - `SandboxFilesystemPathAlreadyExistsError`: the path already exists.
            - `SandboxFilesystemNotADirectoryError`: a path component is not a directory.
            - `SandboxFilesystemPermissionError`: creation is not permitted.
            - `InvalidError`: the operation is not supported by the mount.
            - `SandboxFilesystemError`: the command fails for any other reason.

            **Usage**

            ```python fixture:sandbox
            sandbox.filesystem.make_directory("/tmp/a/b/c")
            ```
            """
            ...

    make_directory: __make_directory_spec
