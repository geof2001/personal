FROM frolvlad/alpine-oraclejdk8:slim

# --- application specific commands ---
ARG P4_CHANGELIST
ARG SERVICE_NAME
ARG BRANCH
ARG BUILD_NUMBER
ARG BUILD_URL
ARG BUILD_TIMESTAMP
ARG VERSION

ADD dist/beehive-apis-*.jar app.jar
RUN sh -c 'touch /app.jar'
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -Djava.security.egd=file:/dev/./urandom -jar /app.jar"]
