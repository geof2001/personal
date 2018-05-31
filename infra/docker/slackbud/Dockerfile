# AlpineLinux with a glibc-2.21 and Oracle Java 8
FROM alpine:3.6
MAINTAINER roku-sr

# Find releases here: https://github.com/sgerrand/alpine-pkg-glibc/releases
ENV GLIBVERSION=2.25-r0
# curl first, because it would fail early if the package location moved
RUN \
    apk --no-cache add curl && \
    curl -Ls https://github.com/sgerrand/alpine-pkg-glibc/releases/download/$GLIBVERSION/glibc-$GLIBVERSION.apk > /tmp/glibc-$GLIBVERSION.apk && \
    curl -Ls https://github.com/sgerrand/alpine-pkg-glibc/releases/download/$GLIBVERSION/glibc-bin-$GLIBVERSION.apk > /tmp/glibc-bin-$GLIBVERSION.apk && \
    curl -Ls https://github.com/patric-r/jvmtop/releases/download/0.8.0/jvmtop-0.8.0.tar.gz > /tmp/jvmtop-0.8.0.tar.gz && \
    curl -Ls https://s3.amazonaws.com/sr-load-test-resources/perf-map-agent.tar.gz > /tmp/perf-map-agent.tar.gz && \
    mkdir -p /util/jvmtop && \
    tar -C /util/jvmtop -xzf /tmp/jvmtop-0.8.0.tar.gz && \
    tar -C /util -xzf /tmp/perf-map-agent.tar.gz && \
    chmod a+x /util/jvmtop/*.sh && \
    apk --no-cache add wget ca-certificates tar python py-pip openssl py-openssl libgcc gnupg bash libuuid rsync && \
    pip install --upgrade pip && \
    pip install awscli && \
    pip install requests_aws_sign && \
    pip install elasticsearch && \
    pip install requests && \
    pip install python-gitlab && \
    pip install requests[security] && \
    pip install pendulum && \
    pip install objdict && \
    apk add --no-cache --allow-untrusted /tmp/glibc-$GLIBVERSION.apk /tmp/glibc-bin-$GLIBVERSION.apk && \
    echo 'hosts: files mdns4_minimal [NOTFOUND=return] dns mdns4' >> /etc/nsswitch.conf &&\
    /usr/glibc-compat/sbin/ldconfig /lib /usr/glibc-compat/lib &&\
    rm -f /tmp/glibc-*.apk && \
    rm -f /tmp/jvmtop-0.8.0.tar.gz && \
    rm -f /tmp/perf-map-agent.tar.gz

# Java Version
ENV JAVA_VERSION_MAJOR 8
ENV JAVA_VERSION_MINOR 131
ENV JAVA_VERSION_BUILD 11
ENV JAVA_PACKAGE       server-jre
ENV JAVA_UUID d54c1d3a095b4ff2b6607d096fa80163
# Download and unarchive Java
RUN mkdir /opt && curl -jksSLH "Cookie: oraclelicense=accept-securebackup-cookie"\
  http://download.oracle.com/otn-pub/java/jdk/${JAVA_VERSION_MAJOR}u${JAVA_VERSION_MINOR}-b${JAVA_VERSION_BUILD}/${JAVA_UUID}/${JAVA_PACKAGE}-${JAVA_VERSION_MAJOR}u${JAVA_VERSION_MINOR}-linux-x64.tar.gz \
    | tar -xzf - -C /opt && \
    ln -s /opt/jdk1.${JAVA_VERSION_MAJOR}.0_${JAVA_VERSION_MINOR} /opt/$JAVA_PACKAGE
# Set environment
ENV JAVA_HOME /opt/$JAVA_PACKAGE
ENV PATH ${PATH}:${JAVA_HOME}/bin
