pipeline {
  agent any
  stages {
    stage('Build') {
     agent {
      dockerfile {
        filename 'Dockerfile'
        args '-p 0.0.0.0:5000:5000 -d --rm'
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
        steps {
            sh '''echo "Run"
            printenv
            docker build --tag planetary-api .
            docker run --rm -d -p 5000:5000 --name planetary-api planetary-api
            '''
            }
        }
    stage('Test') {
      agent any
      steps {
        sh '''echo "Testing"
        '''
      }
    }
  }
}

