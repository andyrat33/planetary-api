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
            flask db_create
            flask db_seed
            python3 -m flask run --host=0.0.0.0 &
           '''
            }
          }
       }
       stage('Test') {
        agent any
            steps {
                 sh '''echo "Testing..."
                 newman  run planetary-api.postman_collection.json -e Planetary-API-Environment.postman_environment.json -r junit,html --reporter-junit-export var/reports/newman/junit/newman.xml --reporter-html-export var/reports/newman/html/index.html

           '''
                 publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'var/reports/newman/html', reportFiles: 'index.html', reportName: 'Newman API Test', reportTitles: ''])

            }

       }
}
