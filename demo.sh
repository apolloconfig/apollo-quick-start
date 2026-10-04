#!/bin/bash

# handle env
if [[ -n "$JAVA_OPTS" ]]; then
  echo JAVA_OPTS = $JAVA_OPTS
fi

if [[ -n "$APOLLO_CONFIG_DB_URL" ]]; then
  echo APOLLO_CONFIG_DB_URL = "$APOLLO_CONFIG_DB_URL"
fi

if [[ -n "$APOLLO_CONFIG_DB_USERNAME" ]]; then
  echo APOLLO_CONFIG_DB_USERNAME = "$APOLLO_CONFIG_DB_USERNAME"
fi

if [[ -n "$APOLLO_CONFIG_DB_PASSWORD" ]]; then
  echo APOLLO_CONFIG_DB_PASSWORD = "${APOLLO_CONFIG_DB_PASSWORD//?/*}"
fi

if [[ -n "$APOLLO_PORTAL_DB_URL" ]]; then
  echo APOLLO_PORTAL_DB_URL = "$APOLLO_PORTAL_DB_URL"
fi

if [[ -n "$APOLLO_PORTAL_DB_USERNAME" ]]; then
  echo APOLLO_PORTAL_DB_USERNAME = "$APOLLO_PORTAL_DB_USERNAME"
fi

if [[ -n "$APOLLO_PORTAL_DB_PASSWORD" ]]; then
  echo APOLLO_PORTAL_DB_PASSWORD = "${APOLLO_PORTAL_DB_PASSWORD//?/*}"
fi

# database platform
spring_profiles_group_github=${SPRING_PROFILES_GROUP_GITHUB:-mysql}

# apollo config db info
apollo_config_db_url=${APOLLO_CONFIG_DB_URL:-"jdbc:mysql://localhost:3306/ApolloConfigDB?characterEncoding=utf8&serverTimezone=Asia/Shanghai"}
apollo_config_db_username=${APOLLO_CONFIG_DB_USERNAME:-root}
apollo_config_db_password=${APOLLO_CONFIG_DB_PASSWORD:-}

# apollo portal db info
apollo_portal_db_url=${APOLLO_PORTAL_DB_URL:-"jdbc:mysql://localhost:3306/ApolloPortalDB?characterEncoding=utf8&serverTimezone=Asia/Shanghai"}
apollo_portal_db_username=${APOLLO_PORTAL_DB_USERNAME:-root}
apollo_portal_db_password=${APOLLO_PORTAL_DB_PASSWORD:-}

# service process and log settings (environment variables override these defaults)
PID_FOLDER=${PID_FOLDER:-.}
LOG_FOLDER=${LOG_FOLDER:-.}
LOG_FILENAME=${LOG_FILENAME:-console.log}
STOP_WAIT_TIME=${STOP_WAIT_TIME:-60}
LOG_APPENDERS=${LOG_APPENDERS:-FILE}
RUN_AS_USER=${RUN_AS_USER:-}

# =============== Please do not modify the following content =============== #

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) windows="1" ;;
  *) windows="0" ;;
esac

# go to script directory
cd "$(dirname "$0")" || exit 1

# meta server url
config_server_url=http://localhost:8080
portal_url=http://localhost:8070

# executable
CURRENT_DIR=$(pwd)
SERVICE_JAR=$CURRENT_DIR/apollo-all-in-one.jar
SERVICE_LOG=$CURRENT_DIR/apollo-service.log
CLIENT_DIR=$CURRENT_DIR/client
CLIENT_JAR=$CLIENT_DIR/apollo-demo.jar

[[ "$PID_FOLDER" == /* ]] || PID_FOLDER="$CURRENT_DIR/$PID_FOLDER"
[[ "$LOG_FOLDER" == /* ]] || LOG_FOLDER="$CURRENT_DIR/$LOG_FOLDER"
SERVICE_PID_DIR=$PID_FOLDER/apollo-service
SERVICE_PID=$SERVICE_PID_DIR/apollo-service.pid
SERVICE_CONSOLE_LOG=$LOG_FOLDER/$LOG_FILENAME

# JAVA OPTS
BASE_JAVA_OPTS="$JAVA_OPTS"
CLIENT_JAVA_OPTS="$BASE_JAVA_OPTS -Dapollo.meta=$config_server_url"
APOLLO_CONFIG_DB_CONFIG=("-Dspring.config-datasource.url=$apollo_config_db_url" "-Dspring.config-datasource.username=$apollo_config_db_username" "-Dspring.config-datasource.password=$apollo_config_db_password")
APOLLO_PORTAL_DB_CONFIG=("-Dspring.portal-datasource.url=$apollo_portal_db_url" "-Dspring.portal-datasource.username=$apollo_portal_db_username" "-Dspring.portal-datasource.password=$apollo_portal_db_password")
H2_CONSOLE_CONFIG="-Dspring.h2.console.enabled=false"
SERVER_JAVA_OPTS=($BASE_JAVA_OPTS "-Dspring.profiles.active=github,database-discovery,auth" "-Dlogging.file.name=$SERVICE_LOG" "-Dspring.profiles.group.github=$spring_profiles_group_github" "${APOLLO_CONFIG_DB_CONFIG[@]}" "${APOLLO_PORTAL_DB_CONFIG[@]}" "$H2_CONSOLE_CONFIG")

function checkServiceTools {
  local tool
  for tool in ps "$@"; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "Required command not found: $tool"
      return 1
    }
  done
}

function switchServiceUser {
  local target_user=$RUN_AS_USER
  local current_uid target_uid target_gid command
  current_uid=$(id -u) || return 1
  if [[ -z "$target_user" && "$current_uid" == "0" && -f "$SERVICE_JAR" ]]; then
    target_user=$(ls -ld "$SERVICE_JAR" | awk '{print $3}')
  fi
  [[ -n "$target_user" ]] || return 0
  target_uid=$(id -u "$target_user") || return 1
  [[ "$target_uid" != "$current_uid" ]] || return 0
  [[ "$current_uid" == "0" ]] || { echo "Cannot run as $target_user: current user is not root."; return 1; }
  if [[ "$1" == "run" && "$(uname -s)" == "Linux" ]]; then
    command -v setpriv >/dev/null 2>&1 || { echo "Required command not found: setpriv (util-linux)"; return 1; }
    target_gid=$(id -g "$target_user") || return 1
  else
    command -v su >/dev/null 2>&1 || { echo "Required command not found: su"; return 1; }
  fi
  mkdir -p "$SERVICE_PID_DIR" "$LOG_FOLDER" || return 1
  touch "$SERVICE_CONSOLE_LOG" || return 1
  chown "$target_user" "$SERVICE_PID_DIR" "$SERVICE_CONSOLE_LOG" || return 1
  if [[ "$1" == "run" && "$(uname -s)" == "Linux" ]]; then
    # Replace the launcher instead of leaving su in front of Java with a 2s stop limit.
    exec setpriv --reuid "$target_uid" --regid "$target_gid" --init-groups "$CURRENT_DIR/demo.sh" "$@"
  fi
  printf -v command '%q ' "$CURRENT_DIR/demo.sh" "$@"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    exec su -m "$target_user" -c "$command"
  else
    exec su -m -s /bin/bash "$target_user" -c "$command"
  fi
}

function checkJava {
  if [[ -n "$JAVA_HOME" ]] && [[ -x "$JAVA_HOME/bin/java" ]];  then
      if [ "$windows" == "1" ]; then
        tmp_java_home=`cygpath -sw "$JAVA_HOME"`
        export JAVA_HOME=`cygpath -u "$tmp_java_home"`
        echo "Windows new JAVA_HOME is: $JAVA_HOME"
      fi
      _java="$JAVA_HOME/bin/java"
  elif type -p java > /dev/null; then
    _java=java
  else
      echo "Could not find java executable, please check PATH and JAVA_HOME variables."
      exit 1
  fi

  if [[ "$_java" ]]; then
      version=$("$_java" -version 2>&1 | awk -F '"' '/version/ {print $2; exit}')
      major_version=${version%%.*}
      major_version=${major_version%%-*}
      if [[ ! "$major_version" =~ ^[0-9]+$ ]] || (( major_version < 17 )); then
          echo "Java version is $version, please make sure Java 17+ is in the path"
          exit 1
      fi
  fi
}

function isServiceRunning {
  [[ "$1" =~ ^[1-9][0-9]*$ ]] && ps -p "$1" > /dev/null 2>&1
}

function startService {
  if [[ -f "$SERVICE_PID" ]]; then
    service_pid=$(cat "$SERVICE_PID")
    if isServiceRunning "$service_pid"; then
      echo "Already running [$service_pid]"
      return 0
    fi
    rm -f "$SERVICE_PID" || return 1
  fi

  [[ -f "$SERVICE_JAR" ]] || { echo "JAR not found: $SERVICE_JAR"; return 1; }
  mkdir -p "$SERVICE_PID_DIR" "$LOG_FOLDER" || return 1
  touch "$SERVICE_CONSOLE_LOG" || return 1
  nohup "$_java" "${SERVER_JAVA_OPTS[@]}" -jar "$SERVICE_JAR" $RUN_ARGS \
    >> "$SERVICE_CONSOLE_LOG" 2>&1 < /dev/null &
  service_pid=$!
  if ! printf '%s\n' "$service_pid" > "$SERVICE_PID"; then
    kill "$service_pid" 2>/dev/null
    return 1
  fi
  echo "Started [$service_pid]"
}

function stopService {
  [[ -f "$SERVICE_PID" ]] || { echo "Not running (pidfile not found)"; return 0; }
  local pid
  pid=$(cat "$SERVICE_PID")
  if ! isServiceRunning "$pid"; then
    echo "Not running (process $pid). Removing stale pid file."
    rm -f "$SERVICE_PID"
    return $?
  fi
  [[ "$STOP_WAIT_TIME" =~ ^[0-9]+$ ]] || { echo "Invalid STOP_WAIT_TIME: $STOP_WAIT_TIME"; return 1; }
  STOP_WAIT_TIME=$((10#$STOP_WAIT_TIME))
  kill "$pid" 2>/dev/null || return 1
  local counter
  for (( counter=0; counter<STOP_WAIT_TIME; counter++ )); do
    if ! isServiceRunning "$pid"; then
      rm -f "$SERVICE_PID" || return 1
      echo "Stopped [$pid]"
      return 0
    fi
    sleep 1
  done
  echo "Unable to stop process $pid in $STOP_WAIT_TIME seconds."
  return 1
}

function checkServerAlive {
  declare -i counter=0
  declare -i max_counter=24 # 24*5=120s
  declare -i total_time=0

  SERVER_URL="$1"

  until [[ (( counter -ge max_counter )) || "$(curl -X GET --silent --connect-timeout 1 --max-time 2 --head "$SERVER_URL" | grep "HTTP")" != "" ]];
  do
    printf "."
    counter+=1
    sleep 5
  done

  total_time=counter*5

  if [[ (( counter -ge max_counter )) ]];
  then
    return $total_time
  fi

  return 0
}

if [ "$1" = "start" ] ; then
  checkServiceTools curl || exit 1
  switchServiceUser "$@" || exit 1
  checkJava
  export LOG_APPENDERS
  echo "==== starting ===="
  echo "Service logging file is $SERVICE_LOG"
  startService

  rc=$?
  if [[ $rc != 0 ]];
  then
    echo "Failed to start service, return code: $rc. Please check $SERVICE_CONSOLE_LOG and $SERVICE_LOG for more information."
    exit $rc;
  fi

  printf "Waiting for service startup"
  checkServerAlive "$portal_url"

  rc=$?
  if [[ $rc != 0 ]];
  then
    printf "\nService failed to start in $rc seconds! Please check %s and %s for more information.\n" "$SERVICE_CONSOLE_LOG" "$SERVICE_LOG"
    exit 1;
  fi

  printf "\nService started. You can visit $portal_url now!\n"

  exit 0;
elif [ "$1" = "run" ] ; then
  switchServiceUser "$@" || exit 1
  checkJava
  export LOG_APPENDERS
  # Keep Java in the foreground so containers forward signals and exit with it.
  exec "$_java" "${SERVER_JAVA_OPTS[@]}" -jar "$SERVICE_JAR" $RUN_ARGS
elif [ "$1" = "client" ] ; then
  checkJava
  if [ "$windows" == "1" ]; then
    "$_java" -classpath "$CLIENT_DIR;$CLIENT_JAR" $CLIENT_JAVA_OPTS com.ctrip.framework.apollo.demo.api.SimpleApolloConfigDemo
  else
    "$_java" -classpath "$CLIENT_DIR:$CLIENT_JAR" $CLIENT_JAVA_OPTS com.ctrip.framework.apollo.demo.api.SimpleApolloConfigDemo
  fi

elif [ "$1" = "stop" ] ; then
  checkServiceTools || exit 1
  echo "==== stopping ===="

  stopService
  exit $?

else
  echo "Usage: demo.sh ( commands ... )"
  echo "commands:"
  echo "  start         start services"
  echo "  run           run services in the foreground"
  echo "  client        start client demo program"
  echo "  stop          stop services"
  exit 1
fi
