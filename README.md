* [快速开始](https://www.apolloconfig.com/#/zh/deployment/quick-start)
* [Quick Start](https://www.apolloconfig.com/#/en/deployment/quick-start)

Apollo 3.0.0 requires Java 17 or later. `apollo-all-in-one.jar` is stored with [Git LFS](https://git-lfs.com/). Install Git LFS and run `git lfs install` before cloning this repository. For an existing clone, run `git lfs install` followed by `git lfs pull` to download the JAR. The `./demo.sh start` command and Docker usage remain the same.

Apollo 3.0.0 需要 Java 17 或更高版本。`apollo-all-in-one.jar` 使用 [Git LFS](https://git-lfs.com/) 存储。克隆仓库前，请安装 Git LFS 并执行 `git lfs install`；已有克隆请执行 `git lfs install` 和 `git lfs pull` 下载 JAR。`./demo.sh start` 命令和 Docker 使用方式不变。

`demo.sh` starts the JAR with `java -jar`. Its configuration section contains the process and log defaults; override them with `PID_FOLDER`, `LOG_FOLDER`, `LOG_FILENAME`, `LOG_APPENDERS`, or `STOP_WAIT_TIME` environment variables. Use `./demo.sh start` / `./demo.sh stop` for background operation, or `./demo.sh run` for foreground operation. The Docker image uses foreground operation so Java receives container stop signals. Release synchronization copies the upstream JAR unchanged.

`demo.sh` 使用 `java -jar` 启动 JAR。进程和日志默认值位于脚本的配置区，可通过 `PID_FOLDER`、`LOG_FOLDER`、`LOG_FILENAME`、`LOG_APPENDERS` 或 `STOP_WAIT_TIME` 环境变量覆盖。使用 `./demo.sh start` / `./demo.sh stop` 在后台启动和停止服务，或使用 `./demo.sh run` 在前台运行。Docker 镜像采用前台运行方式，使 Java 能收到容器停止信号。发布同步流程直接复制上游 JAR，保持其内容不变。

Quote option values containing spaces inside `JAVA_OPTS` or `RUN_ARGS`, for example `JAVA_OPTS='-Xmx512m -Dexample="/path with spaces/value"'`. Options are parsed as quoted words without evaluating shell commands or variable expansions.

`JAVA_OPTS` 或 `RUN_ARGS` 中包含空格的参数值需要使用引号，例如 `JAVA_OPTS='-Xmx512m -Dexample="/path with spaces/value"'`。脚本按带引号的单词解析参数，不执行其中的 shell 命令或变量展开。

Background operation requires `ps`, `curl`, and either `flock` or Perl with native `flock` support; option parsing requires `xargs`. macOS and MSYS/Cygwin can use Perl instead of the `flock` command. Git Bash/Cygwin also uses Windows PowerShell for process identification.

后台运行需要 `ps`、`curl`，以及 `flock` 或支持原生 `flock` 的 Perl；参数解析需要 `xargs`。macOS 和 MSYS/Cygwin 可使用 Perl 替代 `flock` 命令，Git Bash/Cygwin 还使用 Windows PowerShell 识别进程。

Service locks are released automatically when the command exits, including after SIGKILL; a leftover `.lock` directory does not block later commands. `STOP_WAIT_TIME` is interpreted as decimal seconds, including values with leading zeros.

服务锁会在命令退出时自动释放，包括被 SIGKILL 终止的情况；残留的 `.lock` 目录不会阻塞后续命令。`STOP_WAIT_TIME` 按十进制秒数解析，也支持带前导零的值。

When started as root, Java runs as the JAR owner by default; set `RUN_AS_USER` to select another account. On Linux, privilege dropping requires `setpriv` from `util-linux` (included in the Docker image), which preserves Java as PID 1 in foreground containers. The runtime user needs write access to the configured log locations.

以 root 启动时，默认使用 JAR 所属用户运行 Java，可通过 `RUN_AS_USER` 指定其他用户。Linux 下切换用户需要 `util-linux` 提供的 `setpriv`（Docker 镜像已包含），使前台容器中的 Java 仍然是 PID 1。运行用户需要对配置的日志位置具有写权限。
