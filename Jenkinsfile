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
    environment {
        MAIL_USERNAME = credentials('MAIL_USERNAME')
        MAIL_PASSWORD = credentials('MAIL_PASSWORD')
        }
        steps {
            sh '''echo "Run"
            printenv
            docker build --tag planetary-api .
            docker run --rm -d -p 5000:5000 --name planetary-api planetary-api -e ${MAIL_USERNAME} -e ${MAIL_PASSWORD}
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
  }
}

