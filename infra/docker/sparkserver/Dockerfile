FROM 638782101961.dkr.ecr.us-east-1.amazonaws.com/alpine-jre-python:main-bbe64ac056-20170525-32
MAINTAINER roku-sr

EXPOSE 7199 8080

# --- application specific commands ---
ARG P4_CHANGELIST
ARG SERVICE_NAME
ARG BRANCH
ARG BUILD_NUMBER
ARG BUILD_URL
ARG BUILD_TIMESTAMP
ARG VERSION

# the label will be used in Datadog stat prefixed with "docker.*"
LABEL serviceName=$SERVICE_NAME

ENV \
  P4_CHANGELIST=$P4_CHANGELIST \
  SERVICE_NAME=$SERVICE_NAME \
  SERVER_NAME=$SERVICE_NAME \
  BRANCH=$BRANCH \
  BUILD_NUMBER=$BUILD_NUMBER \
  BUILD_URL=$BUILD_URL \
  BUILD_TIMESTAMP=$BUILD_TIMESTAMP \
  VERSION=$VERSION \
  CATALINA_BASE=/usr/$SERVICE_NAME \
  SERVICE_8080_TCP_NAME=$SERVICE_NAME \
  SERVICE_7199_TCP_NAME=$SERVICE_NAME-jmx \
  SERVICE_8080_HEALTHCHECK_URI=/$SERVICE_NAME/healthcheck

COPY dist/ $CATALINA_BASE
COPY log4j2.service.xml $CATALINA_BASE/log4j2.xml
COPY run.sh /usr/local/bin/run.sh
COPY usr.local.bin.rotate_logs_and_push_to_s3.py /usr/local/bin/rotate_logs_and_push_to_s3.py

CMD ["/usr/local/bin/run.sh"]
