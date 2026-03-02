from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as cpactions,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sns as sns,
    # aws_sns_subscriptions as subscriptions,
    aws_ssm as ssm,
    CfnOutput,
)
from constructs import Construct


ACCOUNT = "450372565572"
REGION = "us-east-1"
GITHUB_OWNER = "andyrat33"
GITHUB_REPO = "planetary-api"
GITHUB_BRANCH = "master"
# Update this ARN after creating the CodeStar connection via the AWS Console
CODESTAR_CONNECTION_ARN = (
    "arn:aws:codeconnections:us-east-1:450372565572"
    ":connection/6a48f8fd-f212-407c-99ff-20b201813e1d"
)
DOCKER_SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:450372565572:secret:prod/docker-login-iJ6OPC"
)


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ecr_repo: ecr.Repository,
        ecs_service: ecs.FargateService,
        ecs_cluster: ecs.Cluster,
        alb_dns_name: str,
        alb_sg_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── SSM override parameter ────────────────────────────────────────────
        ssm.StringParameter(
            self,
            "SecurityOverride",
            parameter_name="/planetary-api/pipeline/security-override",
            string_value="false",
            description="Set to 'true' to bypass security gate failures",
        )

        # ── S3 artifacts bucket ───────────────────────────────────────────────
        artifacts_bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # ── SNS approval topic ────────────────────────────────────────────────
        approval_topic = sns.Topic(
            self,
            "ApprovalTopic",
            display_name="Planetary API Pipeline Approval",
        )

        CfnOutput(
            self,
            "ApprovalTopicArn",
            value=approval_topic.topic_arn,
            description="Run: aws sns subscribe --topic-arn <this> "
            "--protocol email --notification-endpoint <your-email>",
        )
        CfnOutput(self, "ArtifactsBucketName", value=artifacts_bucket.bucket_name)

        # ── CodeBuild IAM Role ────────────────────────────────────────────────
        codebuild_role = iam.Role(
            self,
            "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
        )

        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    # ECR
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    # Security Hub
                    "securityhub:BatchImportFindings",
                    "securityhub:GetFindings",
                    # SSM
                    "ssm:GetParameter",
                    # Secrets Manager
                    "secretsmanager:GetSecretValue",
                    # S3
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:GetBucketLocation",
                    # ECS
                    "ecs:UpdateService",
                    "ecs:DescribeServices",
                    # EC2 — ALB security group lockdown
                    "ec2:DescribeSecurityGroups",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress",
                    # CloudWatch Logs
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    # CodeBuild reports
                    "codebuild:CreateReportGroup",
                    "codebuild:CreateReport",
                    "codebuild:UpdateReport",
                    "codebuild:BatchPutTestCases",
                ],
                resources=["*"],
            )
        )

        # ── Shared CodeBuild environment ──────────────────────────────────────
        build_env = codebuild.BuildEnvironment(
            build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            compute_type=codebuild.ComputeType.SMALL,
            privileged=True,  # Required for Docker-in-Docker
            environment_variables={
                "ECR_URI": codebuild.BuildEnvironmentVariable(
                    value=ecr_repo.repository_uri
                ),
                "ARTIFACTS_BUCKET": codebuild.BuildEnvironmentVariable(
                    value=artifacts_bucket.bucket_name
                ),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=ACCOUNT),
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=REGION),
                "ALB_DNS": codebuild.BuildEnvironmentVariable(value=alb_dns_name),
                "ALB_SG_ID": codebuild.BuildEnvironmentVariable(value=alb_sg_id),
            },
        )

        # ── Pipeline variable — optional IP lockdown ──────────────────────────
        allowed_ip_var = codepipeline.Variable(
            variable_name="AllowedIp",
            default_value="none",
            description=(
                "Optional CIDR to restrict ALB inbound access (e.g. 1.2.3.4/32). "
                "Set to 'none' (default) to allow unrestricted access."
            ),
        )

        # ── CodeBuild Projects ────────────────────────────────────────────────
        def make_project(
            name: str, buildspec_file: str, extra_env: dict = None
        ) -> codebuild.PipelineProject:
            env_vars = {}
            if extra_env:
                env_vars.update(extra_env)
            return codebuild.PipelineProject(
                self,
                name,
                project_name=name,
                role=codebuild_role,
                environment=build_env,
                environment_variables=env_vars,
                build_spec=codebuild.BuildSpec.from_source_filename(
                    f"infra/buildspecs/{buildspec_file}"
                ),
            )

        build_project = make_project("PlanetaryBuild", "build.yml")
        semgrep_project = make_project("PlanetarySemgrep", "semgrep.yml")
        snyk_project = make_project("PlanetarySnyk", "snyk_sca.yml")
        postman_security_project = make_project(
            "PlanetaryPostmanSecurity", "postman_security.yml"
        )
        security_gate_project = make_project(
            "PlanetarySecurityGate", "security_gate.yml"
        )
        smoke_test_project = make_project("PlanetarySmokeTest", "smoke_test.yml")
        verify_project = make_project("PlanetaryVerify", "verify.yml")
        lockdown_project = make_project("PlanetaryLockdown", "lockdown.yml")

        # ── Pipeline Artifacts ────────────────────────────────────────────────
        source_artifact = codepipeline.Artifact("SourceArtifact")
        build_artifact = codepipeline.Artifact("BuildArtifact")
        semgrep_artifact = codepipeline.Artifact("SemgrepArtifact")
        snyk_artifact = codepipeline.Artifact("SnykArtifact")
        postman_security_artifact = codepipeline.Artifact("PostmanSecurityArtifact")
        gate_artifact = codepipeline.Artifact("GateArtifact")
        smoke_artifact = codepipeline.Artifact("SmokeArtifact")
        verify_artifact = codepipeline.Artifact("VerifyArtifact")
        lockdown_artifact = codepipeline.Artifact("LockdownArtifact")

        # ── Pipeline ──────────────────────────────────────────────────────────
        pipeline = codepipeline.Pipeline(
            self,
            "PlanetaryPipeline",
            pipeline_name="planetary-api-pipeline",
            pipeline_type=codepipeline.PipelineType.V2,
            variables=[allowed_ip_var],
            artifact_bucket=artifacts_bucket,
            stages=[
                # [1] SOURCE
                codepipeline.StageProps(
                    stage_name="Source",
                    actions=[
                        cpactions.CodeStarConnectionsSourceAction(
                            action_name="GitHub_Source",
                            owner=GITHUB_OWNER,
                            repo=GITHUB_REPO,
                            branch=GITHUB_BRANCH,
                            connection_arn=CODESTAR_CONNECTION_ARN,
                            output=source_artifact,
                        )
                    ],
                ),
                # [2] BUILD
                codepipeline.StageProps(
                    stage_name="Build",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="DockerBuild",
                            project=build_project,
                            input=source_artifact,
                            outputs=[build_artifact],
                        )
                    ],
                ),
                # [3] SECURITY SCAN (parallel)
                codepipeline.StageProps(
                    stage_name="SecurityScan",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="Semgrep_SAST",
                            project=semgrep_project,
                            input=source_artifact,
                            outputs=[semgrep_artifact],
                            run_order=1,
                        ),
                        cpactions.CodeBuildAction(
                            action_name="Snyk_SCA",
                            project=snyk_project,
                            input=source_artifact,
                            outputs=[snyk_artifact],
                            run_order=1,
                        ),
                        cpactions.CodeBuildAction(
                            action_name="Postman_Security",
                            project=postman_security_project,
                            input=source_artifact,
                            extra_inputs=[build_artifact],
                            outputs=[postman_security_artifact],
                            run_order=1,
                        ),
                    ],
                ),
                # [4] SECURITY GATE
                codepipeline.StageProps(
                    stage_name="SecurityGate",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="SecurityGate",
                            project=security_gate_project,
                            input=source_artifact,
                            outputs=[gate_artifact],
                        )
                    ],
                ),
                # [5] MANUAL APPROVAL
                codepipeline.StageProps(
                    stage_name="ManualApproval",
                    actions=[
                        cpactions.ManualApprovalAction(
                            action_name="SecurityReview",
                            notification_topic=approval_topic,
                            additional_information=(
                                "Review Security Hub findings before approving deployment. "
                                f"Console: https://{REGION}.console.aws.amazon.com/securityhub/home"
                                f"?region={REGION}#/findings"
                                f"?search=GeneratorId%3DPREFIX%3Aplanetary-api"
                            ),
                        )
                    ],
                ),
                # [6] SMOKE TEST
                codepipeline.StageProps(
                    stage_name="SmokeTest",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="NewmanSmokeTest",
                            project=smoke_test_project,
                            input=source_artifact,
                            extra_inputs=[build_artifact],
                            outputs=[smoke_artifact],
                        )
                    ],
                ),
                # [7] DEPLOY
                codepipeline.StageProps(
                    stage_name="Deploy",
                    actions=[
                        cpactions.EcsDeployAction(
                            action_name="EcsDeploy",
                            service=ecs_service,
                            image_file=build_artifact.at_path("imagedefinitions.json"),
                        )
                    ],
                ),
                # [8] LOCKDOWN
                codepipeline.StageProps(
                    stage_name="Lockdown",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="SecurityGroupLockdown",
                            project=lockdown_project,
                            input=source_artifact,
                            outputs=[lockdown_artifact],
                            environment_variables={
                                "ALLOWED_IP": codebuild.BuildEnvironmentVariable(
                                    value=allowed_ip_var.reference(),
                                ),
                            },
                        )
                    ],
                ),
                # [9] VERIFY
                codepipeline.StageProps(
                    stage_name="Verify",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="HealthCheck",
                            project=verify_project,
                            input=source_artifact,
                            outputs=[verify_artifact],
                            environment_variables={
                                "ALLOWED_IP": codebuild.BuildEnvironmentVariable(
                                    value=allowed_ip_var.reference(),
                                ),
                            },
                        )
                    ],
                ),
            ],
        )

        # Grant pipeline role access to CodeStar connection
        pipeline.role.add_to_policy(
            iam.PolicyStatement(
                actions=["codestar-connections:UseConnection"],
                resources=[CODESTAR_CONNECTION_ARN],
            )
        )

        CfnOutput(self, "PipelineName", value=pipeline.pipeline_name)
        CfnOutput(self, "PipelineArn", value=pipeline.pipeline_arn)
