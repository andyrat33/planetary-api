pipeline {
  agent any
  stages {
    stage('Install 1Password CLI') {
       steps {
            sh '''
            curl -sSfLo op.zip https://cache.agilebits.com/dist/1P/op2/pkg/v2.16.1/op_linux_amd64_v2.16.1.zip
            unzip -o op.zip
            rm op.zip
            '''
            }
        }
    stage('Build') {
      agent {
        dockerfile {
          filename 'Dockerfile'
          args '--rm -d -p 5000:5000 --name planetary-api'
          additionalBuildArgs '--tag planetary-api'
        }
      }
      environment {
        OP_CONNECT_HOST = 'http://docker1:8080'
        OP_CONNECT_TOKEN = credentials('op_token')
        OP_CLI_PATH = './'
        //MAIL_USERNAME = credentials('MAIL_USERNAME')
        //MAIL_PASSWORD = credentials('MAIL_PASSWORD')
      }
      steps {
        sh '''echo "Test DB Creation after Building..."
        flask db_create
        flask db_seed
           '''
      }
    }

    stage('Run') {
      parallel {
        stage('Run') {
          environment {
            OP_CONNECT_HOST = 'http://docker1:8080'
            OP_CONNECT_TOKEN = credentials('op_token')
            OP_CLI_PATH = './'
          }
          steps {
            sh '''
            echo "Run"
            #docker build --tag planetary-api .
            docker run --env OP_CONNECT_HOST=${OP_CONNECT_HOST} --env OP_CONNECT_TOKEN=${OP_CONNECT_TOKEN} --rm -d -p 5000:5000 --name planetary-api planetary-api
            docker exec planetary-api flask db_create
            docker exec planetary-api flask db_seed
            '''
          }
        }

        stage('SAST Semgrep_agent') {
          agent any

          environment {
            SEMGREP_COMMIT = "${env.GIT_COMMIT}"
//             SEMGREP_REPO_NAME = env.GIT_URL.replaceFirst(/^https:\/\/github.com\/(.*).git$/, '$1')
//             SEMGREP_REPO_URL = env.GIT_URL.replaceFirst(/^(.*).git$/,'$1')
//             SEMGREP_JOB_URL = "${BUILD_URL}"
//             SEMGREP_APP_TOKEN = credentials('SEMGREP_APP_TOKEN')
//             SEMGREP_DEPLOYMENT_ID = credentials('SEMGREP_DEPLOYMENT_ID')
//             SEMGREP_BRANCH = "${GIT_BRANCH}"
          }
          steps {
             sh 'pip3 install semgrep'
             sh 'python3 --version'
             sh 'semgrep --version'
             sh 'semgrep ci'
             //sh 'python -m semgrep_agent --publish-token $SEMGREP_APP_TOKEN --publish-deployment $SEMGREP_DEPLOYMENT_ID'
          }
        }

      }
    }

    stage('Smoke Test') {
      agent any
      steps {
        sh '''echo "Smoke Tests"
        curl -s -XGET http://localhost:5000/planet_details/1 | jq .
        curl -s -X GET --location "http://localhost:5000/planet_details/2" | jq .
        '''
      }
    }

    stage('Postman Tests') {
      agent any
      steps {
        sh 'echo "Postman Testing"'
        nodejs('NodeJS') {
          sh 'npm install -g newman-reporter-htmlextra'
          sh 'newman run planetary-api.postman_collection.json -e Planetary-API-Environment.postman_environment.json --reporters cli,junit,htmlextra --reporter-junit-export "report.xml" --suppress-exit-code'
        }

        junit(healthScaleFactor: 0.9, keepLongStdio: true, testResults: '**/report.xml')
        archiveArtifacts(artifacts: 'newman/**/*planetary-api-*.html', fingerprint: true)
      }
    }

    stage('Dependency Track') {
      agent any
      steps {
        sh '''echo "SBOM Creation"
        VENV=\'venv\'
        python3 -m venv $VENV
        . $VENV/bin/activate
        pip3 install cyclonedx-bom
        cyclonedx-py -o ${WORKSPACE}/bom.xml
        echo "Publish Dependency Track"
        '''
        withCredentials(bindings: [string(credentialsId: 'Dependency-Track-Automation', variable: 'API_KEY')]) {
          dependencyTrackPublisher(artifact: '${WORKSPACE}/bom.xml', synchronous: true, autoCreateProjects: true, dependencyTrackApiKey: API_KEY, projectName: 'planetary-api', projectVersion: '1')
        }

      }
    }

    stage('Dependency Checks') {
      steps {
        dependencyCheck(odcInstallation: 'dependency-check', additionalArguments: "--scan ${env.WORKSPACE}")
        dependencyCheckPublisher(pattern: '**/dependency-check-report.xml')
      }
    }

  }
  post {
    always {
      sh '''echo "Stopping Container"
            docker stop planetary-api || exit 0
            '''
    }

  }
}
