pipeline {

  stages {
  agent {
    dockerfile {
      filename 'Dockerfile'
    }

  }
    stage('Build') {
      steps {
        sh '''echo "Building..."
        python3 -m flask run --host=0.0.0.0'''
      }
    }

  }
}