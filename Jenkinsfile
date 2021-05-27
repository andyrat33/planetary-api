pipeline {
  agent {dockerfile { filename 'Dockerfile' }}
  environment {
  MAIL_USERNAME = credentials('MAIL_USERNAME')
  MAIL_PASSWORD = credentials('MAIL_PASSWORD')
  }
    stages {
        stage('Build') {
            steps {
            sh '''echo "Building..."
            python3 -m flask run --host=0.0.0.0
            flask create_db
            flask seed_db'''
            }
          }
       }
}
