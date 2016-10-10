#!/bin/sh

# apollo config db info
apollo_config_db_url=jdbc:mysql://localhost:3306/ApolloConfigDB?characterEncoding=utf8
apollo_config_db_username=root
apollo_config_db_password=

# apollo portal db info
apollo_portal_db_url=jdbc:mysql://localhost:3306/ApolloPortalDB?characterEncoding=utf8
apollo_portal_db_username=root
apollo_portal_db_password=

# =============== Please do not modify the following content =============== #

# meta server url
config_server_url=http://localhost:8080
admin_server_url=http://localhost:8090
eureka_service_url=$config_server_url/eureka/
portal_url=http://localhost:8070

# JAVA OPTS
export BASE_JAVA_OPTS="-Denv=dev -Dspring.profiles.active=dev -Deureka.service.url=$eureka_service_url -Ddev_meta=$config_server_url"

# executable
JAR_FILE=apollo-all-in-one.jar
SERVICE_DIR=./service
SERVICE_JAR_NAME=apollo-service.jar
SERVICE_JAR=$SERVICE_DIR/$SERVICE_JAR_NAME
PORTAL_DIR=./portal
PORTAL_JAR_NAME=apollo-portal.jar
PORTAL_JAR=$PORTAL_DIR/$PORTAL_JAR_NAME
CLIENT_DIR=./client
CLIENT_JAR=$CLIENT_DIR/apollo-demo.jar

function checkServerAlive {
  declare -i counter=0
  declare -i max_counter=24 # 24*5=120s
  declare -i total_time=0

  SERVER_URL="$1"

  until [[ (( counter -ge max_counter )) || "$(curl -X GET --silent --connect-timeout 1 --head $SERVER_URL | grep "Coyote")" != "" ]];
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
  echo "==== starting service ===="
  export JAVA_OPTS="$BASE_JAVA_OPTS -Dspring.datasource.url=$apollo_config_db_url -Dspring.datasource.username=$apollo_config_db_username -Dspring.datasource.password=$apollo_config_db_password"

  if [[ -f $SERVICE_JAR ]]; then
    rm -rf $SERVICE_JAR
  fi

  ln $JAR_FILE $SERVICE_JAR
  chmod a+x $SERVICE_JAR

  $SERVICE_JAR start --configservice --adminservice

  rc=$?
  if [[ $rc != 0 ]];
  then
    echo "Failed to start service, return code: $rc"
    exit $rc;
  fi

  printf "Waiting for config service startup"
  checkServerAlive $config_server_url

  rc=$?
  if [[ $rc != 0 ]];
  then
    printf "\nConfig service failed to start in $rc seconds!\n"
    exit 1;
  fi

  printf "\nConfig service started. You may visit $config_server_url for service status now!\n"

  printf "Waiting for admin service startup"
  checkServerAlive $admin_server_url

  rc=$?
  if [[ $rc != 0 ]];
  then
    printf "\nAdmin service failed to start in $rc seconds!\n"
    exit 1;
  fi

  printf "\nAdmin service started\n"

  echo "==== starting portal ===="
  export JAVA_OPTS="$BASE_JAVA_OPTS -Dserver.port=8070 -Dspring.datasource.url=$apollo_portal_db_url -Dspring.datasource.username=$apollo_portal_db_username -Dspring.datasource.password=$apollo_portal_db_password"

  if [[ -f $PORTAL_JAR ]]; then
    rm -rf $PORTAL_JAR
  fi

  ln $JAR_FILE $PORTAL_JAR
  chmod a+x $PORTAL_JAR

  $PORTAL_JAR start --portal

  rc=$?
  if [[ $rc != 0 ]];
  then
    echo "Failed to start portal, return code: $rc"
    exit $rc;
  fi

  printf "Waiting for portal startup"
  checkServerAlive $portal_url

  rc=$?
  if [[ $rc != 0 ]];
  then
    printf "\nPortal failed to start in $rc seconds!\n"
    exit 1;
  fi

  printf "\nPortal started. You can visit $portal_url now!\n"

  exit 0;
elif [ "$1" = "client" ] ; then
  java -classpath $CLIENT_DIR:$CLIENT_JAR $BASE_JAVA_OPTS SimpleApolloConfigDemo

  exit 0;
elif [ "$1" = "stop" ] ; then
  echo "==== stopping portal ===="
  cd $PORTAL_DIR
  ./$PORTAL_JAR_NAME stop

  cd ..

  echo "==== stopping service ===="
  cd $SERVICE_DIR
  ./$SERVICE_JAR_NAME stop

  exit 0;
else
  echo "Usage: build.sh ( commands ... )"
  echo "commands:"
  echo "  start         start services and portal"
  echo "  client        start client demo program"
  echo "  stop          stop services and portal"
  exit 1
fi
