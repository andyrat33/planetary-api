pipeline {
  agent any
  stages {
    stage('Build') {
     agent {
      dockerfile {
        filename 'Dockerfile'
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

