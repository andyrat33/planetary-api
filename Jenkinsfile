pipeline {
  agent any
  stages {
    stage('Build') {
     agent {
      dockerfile {
        filename 'Dockerfile'
        args '--rm -d -p 5000:5000 --name planetary-api'
        additionalBuildArgs  '--tag planetary-api'
        }
      }
      environment {
        MAIL_USERNAME = credentials('MAIL_USERNAME')
        MAIL_PASSWORD = credentials('MAIL_PASSWORD')
        }

      steps {
        sh '''echo "Test DB Creation after Building..."
        flask db_create
        flask db_seed
           '''
         }
       }
    stage('Run') {
    environment {
        MAIL_USERNAME = credentials('MAIL_USERNAME')
        MAIL_PASSWORD = credentials('MAIL_PASSWORD')
        }
        steps {
            sh '''echo "Run"
            #docker build --tag planetary-api .
            docker run --env MAIL_USERNAME=${MAIL_USERNAME} --env MAIL_PASSWORD=${MAIL_PASSWORD} --rm -d -p 5000:5000 --name planetary-api planetary-api
            docker exec planetary-api flask db_create
            docker exec planetary-api flask db_seed
            '''
            }
        }
    stage('Smoke Test') {
      agent any
      steps {
        sh '''echo "Smoke Tests"
        curl -XGET http://localhost:5000/planet_details/1 | jq .
        curl -X GET --location "http://localhost:5000/planet_details/2" | jq .
        '''
      }
    }
    stage('Postman Tests') {
      agent any
      steps {
        sh '''echo "Testing"
        curl -XGET http://localhost:5000/planet_details/3 | json_pp
        '''
        nodejs(nodeJSInstallationName: 'NodeJS') {
        sh 'newman run planetary-api.postman_collection.json -e Planetary-API-Environment.postman_environment.json --reporters cli,junit,html --reporter-junit-export "newmman/report.xml" --reporter-html-export "newman/report.html"'
        }
        junit "newman/report.xml"
      }
    }
     stage('Shutdown') {
      agent any
      steps {
        sh '''echo "Stopping Container"
        docker stop planetary-api
        '''
      }
    }
  }
}

