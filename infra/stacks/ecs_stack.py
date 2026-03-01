from aws_cdk import (
    Stack,
    Duration,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
)
from constructs import Construct


class EcsStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, ecr_repo: ecr.Repository, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC with 2 AZs
        vpc = ec2.Vpc(
            self,
            "PlanetaryVpc",
            max_azs=2,
            nat_gateways=1,
        )

        # ECS Cluster
        self.cluster = ecs.Cluster(
            self,
            "PlanetaryCluster",
            vpc=vpc,
            cluster_name="planetary-api-cluster",
        )

        # Fargate Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "PlanetaryTaskDef",
            cpu=512,
            memory_limit_mib=1024,
        )

        # Note: ECR pull permissions are granted automatically by CDK
        # when using ContainerImage.from_ecr_repository()

        # Reference existing DB credentials from Secrets Manager
        # (created separately or by RDS — pass endpoint via env var)
        db_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "DbSecret",
            secret_name="planetary-api/db-credentials",
        )

        # Container definition
        container = task_definition.add_container(
            "planetary-api",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo, tag="latest"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="planetary-api"),
            environment={
                "MAIL_SERVER": "localhost",
                "MAIL_PORT": "1025",
                "MAIL_USE_TLS": "false",
            },
            secrets={
                "DB_USER": ecs.Secret.from_secrets_manager(db_secret, "DB_USER"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(
                    db_secret, "DB_PASSWORD"
                ),
                "DB_HOST": ecs.Secret.from_secrets_manager(db_secret, "DB_HOST"),
                "DB_NAME": ecs.Secret.from_secrets_manager(db_secret, "DB_NAME"),
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:5000/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        container.add_port_mappings(ecs.PortMapping(container_port=5000))

        # ALB + Fargate Service
        alb_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "PlanetaryService",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            assign_public_ip=False,
        )

        # Health check path
        alb_service.target_group.configure_health_check(
            path="/",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
        )

        self.service = alb_service.service

        CfnOutput(self, "ServiceArn", value=self.service.service_arn)
        CfnOutput(self, "ClusterArn", value=self.cluster.cluster_arn)
        CfnOutput(
            self, "AlbDnsName", value=alb_service.load_balancer.load_balancer_dns_name
        )
