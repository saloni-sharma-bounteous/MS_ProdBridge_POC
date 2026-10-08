FROM eclipse-temurin:{{java_version}}-jre
RUN groupadd --system app && useradd --system --gid app --no-create-home app
WORKDIR /app
COPY target/{{artifact_id}}-*.jar /app/app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/app.jar"]
