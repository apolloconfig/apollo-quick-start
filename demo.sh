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

# =============== Please do not modify the following content =============== #

if [ "$(uname)" == "Darwin" ]; then
    windows="0"
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    windows="0"
elif [ "$(expr substr $(uname -s) 1 5)" == "MINGW" ]; then
    windows="1"
else
    windows="0"
fi

# go to script directory
cd "${0%/*}"

# meta server url
config_server_url=http://localhost:8080
portal_url=http://localhost:8070

# executable
CURRENT_DIR=$(pwd)
SERVICE_JAR=$CURRENT_DIR/apollo-all-in-one.jar
SERVICE_LOG=$CURRENT_DIR/apollo-service.log
CLIENT_DIR=$CURRENT_DIR/client
CLIENT_JAR=$CLIENT_DIR/apollo-demo.jar

# JAVA OPTS
BASE_JAVA_OPTS="$JAVA_OPTS"
CLIENT_JAVA_OPTS="$BASE_JAVA_OPTS -Dapollo.meta=$config_server_url"
APOLLO_CONFIG_DB_CONFIG="-Dspring.config-datasource.url=$apollo_config_db_url -Dspring.config-datasource.username=$apollo_config_db_username -Dspring.config-datasource.password=$apollo_config_db_password"
APOLLO_PORTAL_DB_CONFIG="-Dspring.portal-datasource.url=$apollo_portal_db_url -Dspring.portal-datasource.username=$apollo_portal_db_username -Dspring.portal-datasource.password=$apollo_portal_db_password"
SERVER_JAVA_OPTS="$BASE_JAVA_OPTS -Dspring.profiles.active=github,database-discovery,auth -Dlogging.file.name=$SERVICE_LOG -Dspring.profiles.group.github=$spring_profiles_group_github $APOLLO_CONFIG_DB_CONFIG $APOLLO_PORTAL_DB_CONFIG"

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
      version=$("$_java" -version 2>&1 | awk -F '"' '/version/ {print $2}')
      version_in_digit=$(echo "$version" | awk -F. '{printf("%03d%03d",$1,$2);}')
      if [[ $version_in_digit < 001008 ]]; then
          echo "Java version is $version, please make sure java 1.8+ is in the path"
          exit 1
      fi
  fi
}

function checkServerAlive {
  declare -i counter=0
  declare -i max_counter=24 # 24*5=120s
  declare -i total_time=0

  SERVER_URL="$1"

  until [[ (( counter -ge max_counter )) || "$(curl -X GET --silent --connect-timeout 1 --max-time 2 --head $SERVER_URL | grep "HTTP")" != "" ]];
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

checkJava

if [ "$1" = "start" ] ; then
  echo "==== starting ===="
  echo "Service logging file is $SERVICE_LOG"
  export APP_NAME="apollo-service"
  export JAVA_OPTS="$SERVER_JAVA_OPTS"

  $SERVICE_JAR start

  rc=$?
  if [[ $rc != 0 ]];
  then
    echo "Failed to start service, return code: $rc. Please check $SERVICE_LOG for more information."
    exit $rc;
  fi

  printf "Waiting for service startup"
  checkServerAlive $portal_url

  rc=$?
  if [[ $rc != 0 ]];
  then
    printf "\nService failed to start in $rc seconds! Please check $SERVICE_LOG for more information.\n"
    exit 1;
  fi

  printf "\nService started. You can visit $portal_url now!\n"

  exit 0;
elif [ "$1" = "client" ] ; then
  if [ "$windows" == "1" ]; then
    java -classpath "$CLIENT_DIR;$CLIENT_JAR" $CLIENT_JAVA_OPTS com.ctrip.framework.apollo.demo.api.SimpleApolloConfigDemo
  else
    java -classpath $CLIENT_DIR:$CLIENT_JAR $CLIENT_JAVA_OPTS com.ctrip.framework.apollo.demo.api.SimpleApolloConfigDemo
  fi

elif [ "$1" = "stop" ] ; then
  echo "==== stopping ===="

  export APP_NAME="apollo-service"
  $SERVICE_JAR stop

else
  echo "Usage: demo.sh ( commands ... )"
  echo "commands:"
  echo "  start         start services"
  echo "  client        start client demo program"
  echo "  stop          stop services"
  exit 1
fi
