ARG basePythonOSVersion=3.12.13
ARG baseNodeVersion=20

# ── Stage 0: Frontend build — compile the landing page SPA ───────────
# Builds `frontend/` (Vite + React + TS) and emits hashed bundles to
# `/build/frontend/dist`. Only `package*.json` is copied first so npm's
# install layer caches independently of source-file edits.
FROM hub.docker.prod.walmart.com/library/node:${baseNodeVersion} AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ── Stage 1: Python base — install deps from Walmart Artifactory ─────
FROM hub.docker.prod.walmart.com/library/python:${basePythonOSVersion} AS prepare-stage

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code
COPY requirements.txt requirements.txt

RUN pip3 config --user set global.extra-index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/devtools-pypi/simple && \
    pip3 config --user set global.index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/pythonhosted-pypi-release-remote/simple && \
    pip3 config --user set global.trusted-host pypi.ci.artifacts.walmart.com && \
    pip3 install --no-cache-dir -r requirements.txt

EXPOSE 8000
COPY . .

# ── Stage 2: Test — unit tests → coverage.xml + JUnit XML for TestHub ─
FROM prepare-stage AS test_stage
ARG cpd
ARG BUILDURL
ARG LOOPERID

RUN echo "Inside test container — CONCORDID=${cpd} LOOPERID=${LOOPERID} BUILDURL=${BUILDURL}"

# Execute unit tests — generate both coverage.xml and JUnit XML for Gatekeeper evidence.
# The walmart-devtools-pytest-reporter-testburst plugin ships in requirements.txt and
# auto-activates via pytest's entry_points discovery to upload results to TestHub.
RUN export CONCORDID=${cpd} LOOPERID=${LOOPERID} BUILDURL=${BUILDURL} && \
    python3 -m pytest \
        --cov=agent_factory \
        --cov=storage \
        --cov-report xml:coverage.xml \
        --cov-config=.coveragerc \
        --junitxml=test-results.xml \
        tests/unit/

# ── Stage 3: SonarQube scanner ───────────────────────────────────────
FROM docker.ci.artifacts.walmart.com/strati-docker/docker-sonarqube-scanner:0.0.28 AS sonar_stage
ARG sonarOpts
ARG sonarBranchOpts
ARG sonarPROpts
ARG pullRequestId
ARG eventType
ARG job_name
ARG job_url
ARG jenkins_url
ARG LOOPERID
ARG github_repo_git_url
ARG github_branch_name
ARG looper_job_type

ENV JOB_NAME=$job_name
ENV JOB_URL=$job_url
ENV JENKINS_URL=$jenkins_url
ENV LOOPER_RUN_ID=$LOOPERID
ENV GITHUB_REPO_GIT_URL=$github_repo_git_url
ENV GITHUB_BRANCH_NAME=$github_branch_name
ENV LOOPER_JOB_TYPE=$looper_job_type

# Install Java 17 for SonarQube compatibility
RUN export http_proxy=http://sysproxy.wal-mart.com:8080 && \
    export https_proxy=http://sysproxy.wal-mart.com:8080 && \
    apt-get update && \
    apt-get install -y openjdk-17-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

COPY --from=test_stage /code /code
WORKDIR /code
RUN echo ${sonarOpts} ${sonarBranchOpts} ${sonarPROpts}
RUN if [ "$eventType" = "push" ] ; then \
        sonar-scanner --debug ${sonarOpts} ${sonarBranchOpts} -Dsonar.scanner.metadataFilePath=/tmp/report-task.txt; \
    else \
        export prId=$(echo "$pullRequestId" | tr -d '[]'); \
        sonar-scanner --debug -Dsonar.pullrequest.key=${prId} ${sonarOpts} ${sonarPROpts} -Dsonar.scanner.metadataFilePath=/tmp/report-task.txt; \
    fi

# Send Sonar results to TestHub
RUN eval "curl -k --location 'https://sonarlooperproducer.walmart.com/looper-sonar-results' --form 'sonarResultsFile=@\"/tmp/report-task.txt\"' --form 'jobName=\"${JOB_NAME}\"' --form 'jobUrl=\"${JOB_URL}\"' --form 'instanceUrl=\"${JENKINS_URL}\"' --form 'buildUUID=\"${LOOPER_RUN_ID}\"' --form 'gitUrl=\"${GITHUB_REPO_GIT_URL}\"' --form 'gitBranch=\"${GITHUB_BRANCH_NAME}\"' --form 'jobType=\"${LOOPER_JOB_TYPE}\"'"

# ── Stage 4: Walmart SSL certificates ────────────────────────────────
FROM docker.prod.walmart.com/wce/ca-roots:latest AS ssl-certificates

# ── Stage 5: Production runtime ───────────────────────────────────────
FROM prepare-stage AS run_stage

COPY --from=ssl-certificates /usr/local/share/ca-certificates /usr/local/share/ca-certificates
COPY --from=ssl-certificates /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

WORKDIR /code

# Drop dev-only directories from the production image. The frontend
# source tree (src/, node_modules/, vite.config.ts, etc.) is not needed
# at runtime — only the compiled `dist/` is, and it comes from the
# dedicated `frontend-build` stage below.
RUN rm -rf /code/tests /code/scripts /code/frontend 2>/dev/null || true

# Replant the built homepage so FastAPI's StaticFiles mount can serve
# it from `frontend/dist/`. `agent_factory/api/homepage.py` resolves
# the directory relative to the repo root.
COPY --from=frontend-build /build/frontend/dist /code/frontend/dist

RUN adduser app --uid 10000 && chown -R app:app /code
EXPOSE 8000
USER 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
