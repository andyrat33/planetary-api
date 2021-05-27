pipeline {
  agent {dockerfile { filename 'Dockerfile' }}
    stages {
        stage {
            steps {
            sh '''echo "Building..."
            python3 -m flask run --host=0.0.0.0'''
            }
          }
       }
}
