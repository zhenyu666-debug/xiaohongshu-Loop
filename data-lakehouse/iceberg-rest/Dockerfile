FROM tabulario/iceberg-rest:1.5.2

USER root

RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

RUN cd /tmp && \
    unzip -q -o /usr/lib/iceberg-rest/iceberg-rest-image-all.jar -d /usr/lib/iceberg-rest/extracted && \
    rm /usr/lib/iceberg-rest/iceberg-rest-image-all.jar

COPY ./lib/hadoop-aws-3.3.6.jar /usr/lib/iceberg-rest/extra/
COPY ./lib/aws-java-sdk-bundle-1.12.772.jar /usr/lib/iceberg-rest/extra/
COPY ./lib/aws-sdk-v2-bundle-2.24.0.jar /usr/lib/iceberg-rest/extra/

# Wrapper script to start with extended classpath.
# Note: /extracted holds the unzipped fat-jar (loose class files), so the
# directory itself (not /*) must be on the classpath.
RUN printf '#!/bin/sh\nexec java -cp "/usr/lib/iceberg-rest/extracted:/usr/lib/iceberg-rest/extra/*" org.apache.iceberg.rest.RESTCatalogServer "$@"\n' > /usr/lib/iceberg-rest/start.sh && \
    chmod +x /usr/lib/iceberg-rest/start.sh

WORKDIR /usr/lib/iceberg-rest
USER iceberg

ENTRYPOINT ["/usr/lib/iceberg-rest/start.sh"]
