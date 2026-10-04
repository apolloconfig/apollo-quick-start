* [快速开始](https://www.apolloconfig.com/#/zh/deployment/quick-start)
* [Quick Start](https://www.apolloconfig.com/#/en/deployment/quick-start)

Apollo 3.0.0 requires Java 17 or later. `apollo-all-in-one.jar` is stored with [Git LFS](https://git-lfs.com/). Install Git LFS and run `git lfs install` before cloning this repository. For an existing clone, run `git lfs install` followed by `git lfs pull` to download the JAR. The `./demo.sh start` command and Docker usage remain the same.

Apollo 3.0.0 需要 Java 17 或更高版本。`apollo-all-in-one.jar` 使用 [Git LFS](https://git-lfs.com/) 存储。克隆仓库前，请安装 Git LFS 并执行 `git lfs install`；已有克隆请执行 `git lfs install` 和 `git lfs pull` 下载 JAR。`./demo.sh start` 命令和 Docker 使用方式不变。

`demo.sh` starts the JAR with `java -jar`. Its configuration section contains the process and log defaults; override them with `PID_FOLDER`, `LOG_FOLDER`, `LOG_FILENAME`, `LOG_APPENDERS`, or `STOP_WAIT_TIME` environment variables. Use `./demo.sh start` / `./demo.sh stop` for background operation, or `./demo.sh run` for foreground operation. The Docker image uses foreground operation so Java receives container stop signals. Release synchronization copies the upstream JAR unchanged.

`demo.sh` 使用 `java -jar` 启动 JAR。进程和日志默认值位于脚本的配置区，可通过 `PID_FOLDER`、`LOG_FOLDER`、`LOG_FILENAME`、`LOG_APPENDERS` 或 `STOP_WAIT_TIME` 环境变量覆盖。使用 `./demo.sh start` / `./demo.sh stop` 在后台启动和停止服务，或使用 `./demo.sh run` 在前台运行。Docker 镜像采用前台运行方式，使 Java 能收到容器停止信号。发布同步流程直接复制上游 JAR，保持其内容不变。

`JAVA_OPTS` and `RUN_ARGS` retain the old launcher's whitespace-separated option format, for example `JAVA_OPTS='-Xms128m -Xmx512m'`. Quotes inside these variables are passed literally. Run background `start` and `stop` commands sequentially. On Linux/macOS, the recorded PID must match this Apollo JAR, and zombie processes count as stopped; Git Bash/Cygwin retains the old PID-existence check. Startup continues to poll the Portal endpoint for up to 120 seconds. `STOP_WAIT_TIME` is interpreted as decimal seconds, including values with leading zeros.

`JAVA_OPTS` 和 `RUN_ARGS` 延续旧启动器按空白分隔参数的格式，例如 `JAVA_OPTS='-Xms128m -Xmx512m'`；变量内部的引号会按原样传递。后台 `start` 和 `stop` 命令应顺序执行。Linux/macOS 会确认记录的 PID 对应当前 Apollo JAR，并将僵尸进程视为已停止；Git Bash/Cygwin 延续旧版仅检查 PID 是否存在的方式。启动时继续等待 Portal HTTP 响应，最长 120 秒。`STOP_WAIT_TIME` 按十进制秒数解析，也支持带前导零的值。

Background operation requires `ps` and `curl`. When started as root, Java runs as the JAR owner by default; set `RUN_AS_USER` to select another account. Background startup uses `su`; Linux foreground privilege dropping uses `setpriv` from `util-linux` (included in the Docker image) to preserve Java as PID 1. The runtime user needs write access to the configured log locations.

后台运行需要 `ps` 和 `curl`。以 root 启动时，默认使用 JAR 所属用户运行 Java，可通过 `RUN_AS_USER` 指定其他用户。后台启动使用 `su`；Linux 前台运行时切换用户使用 `util-linux` 提供的 `setpriv`（Docker 镜像已包含），使 Java 仍然是 PID 1。运行用户需要对配置的日志位置具有写权限。
