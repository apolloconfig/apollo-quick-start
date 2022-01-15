# Dockerfile for apollo quick start
# Build with:
# docker build -t nobodyiam/apollo-quick-start .
# Run with:
# docker-compose up

FROM openjdk:8-jre-alpine
MAINTAINER nobodyiam<https://github.com/nobodyiam>

COPY apollo-all-in-one.jar /apollo-quick-start/apollo-all-in-one.jar
COPY client /apollo-quick-start/client
COPY demo.sh /apollo-quick-start/demo.sh
COPY portal/apollo-portal.conf /apollo-quick-start/portal/apollo-portal.conf
COPY service/apollo-service.conf /apollo-quick-start/service/apollo-service.conf

EXPOSE 8070 8080

RUN echo "http://mirrors.aliyun.com/alpine/v3.6/main" > /etc/apk/repositories \
    && echo "http://mirrors.aliyun.com/alpine/v3.6/community" >> /etc/apk/repositories \
    && apk update upgrade \
    && apk add --no-cache curl bash \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && sed -i'.bak' '/db_url/s/localhost/apollo-db/g' /apollo-quick-start/demo.sh \
    && sed -i "s/exit 0;/tail -f \/dev\/null/g" /apollo-quick-start/demo.sh

CMD ["/apollo-quick-start/demo.sh", "start"]
