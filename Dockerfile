# Dockerfile for apollo quick start
# Build with:
# docker build -t nobodyiam/apollo-quick-start .
# Run with:
# docker-compose up
# or if you are using a machine with an ARM architecture, such as a Mac M1, run with:
# docker-compose -f docker-compose-arm64.yml up

FROM eclipse-temurin:17-jre

LABEL maintainer="nobodyiam<https://github.com/nobodyiam>"

# Copy necessary files into the image
COPY apollo-all-in-one.jar /apollo-quick-start/apollo-all-in-one.jar
COPY apollo-all-in-one.conf /apollo-quick-start/apollo-all-in-one.conf
COPY client /apollo-quick-start/client
COPY demo.sh /apollo-quick-start/demo.sh

# Expose the necessary ports
EXPOSE 8070 8080

# Install dependencies, set timezone, and modify the demo.sh script
RUN apt-get update && \
    apt-get install -y curl bash tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Set the timezone to Asia/Shanghai
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    # Modify demo.sh script
    sed -i'.bak' '/db_url/s/localhost/apollo-db/g' /apollo-quick-start/demo.sh && \
    sed -i "s/exit 0;/tail -f \/dev\/null/g" /apollo-quick-start/demo.sh

# Set the default command to execute the demo.sh script
CMD ["/apollo-quick-start/demo.sh", "start"]
