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
        sh '''echo "Building..."
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
    stage('Test') {
      agent any
      steps {
        sh '''echo "Testing"
        curl -XGET http://localhost:5000/
        '''
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

