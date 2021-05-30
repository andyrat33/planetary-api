pipeline {
  agent any
  stages {
    stage('Build') {
     agent {
      dockerfile {
        filename 'Dockerfile'
        label 'planetary-api'
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
        python3 -m flask run --host=0.0.0.0 &
           '''
         }
       }
    stage('Run') {
        steps {
            sh '''echo "Run"
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

