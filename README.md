* [快速开始](https://www.apolloconfig.com/#/zh/deployment/quick-start)
* [Quick Start](https://www.apolloconfig.com/#/en/deployment/quick-start)

Apollo 3.0.0 requires Java 17 or later. `apollo-all-in-one.jar` is stored with [Git LFS](https://git-lfs.com/). Install Git LFS and run `git lfs install` before cloning this repository. For an existing clone, run `git lfs install` followed by `git lfs pull` to download the JAR. The `./demo.sh start` command and Docker usage remain the same.

Apollo 3.0.0 需要 Java 17 或更高版本。`apollo-all-in-one.jar` 使用 [Git LFS](https://git-lfs.com/) 存储。克隆仓库前，请安装 Git LFS 并执行 `git lfs install`；已有克隆请执行 `git lfs install` 和 `git lfs pull` 下载 JAR。`./demo.sh start` 命令和 Docker 使用方式不变。

`demo.sh` starts the JAR with `java -jar`. Its configuration section contains the process and log defaults; override them with `PID_FOLDER`, `LOG_FOLDER`, `LOG_FILENAME`, `LOG_APPENDERS`, or `STOP_WAIT_TIME` environment variables. Use `./demo.sh start` / `./demo.sh stop` for background operation, or `./demo.sh run` for foreground operation. The Docker image uses foreground operation so Java receives container stop signals. Release synchronization copies the upstream JAR unchanged.

`demo.sh` 使用 `java -jar` 启动 JAR。进程和日志默认值位于脚本的配置区，可通过 `PID_FOLDER`、`LOG_FOLDER`、`LOG_FILENAME`、`LOG_APPENDERS` 或 `STOP_WAIT_TIME` 环境变量覆盖。使用 `./demo.sh start` / `./demo.sh stop` 在后台启动和停止服务，或使用 `./demo.sh run` 在前台运行。Docker 镜像采用前台运行方式，使 Java 能收到容器停止信号。发布同步流程直接复制上游 JAR，保持其内容不变。
