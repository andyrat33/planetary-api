from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    aws_rds as rds,
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

        # RDS security group — ingress from ECS tasks added after service creation
        rds_sg = ec2.SecurityGroup(
            self,
            "RdsSg",
            vpc=vpc,
            description="MySQL access from ECS tasks",
        )

        # RDS MySQL 8.0 — RemovalPolicy.DESTROY for easy teardown (educational tool)
        db = rds.DatabaseInstance(
            self,
            "PlanetaryDb",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[rds_sg],
            database_name="planetary",
            credentials=rds.Credentials.from_generated_secret(
                "admin",
                secret_name="planetary-api/db-credentials",
            ),
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
            backup_retention=Duration.days(0),
            multi_az=False,
        )

        # Destroy the credentials secret when the stack is deleted
        db.secret.apply_removal_policy(RemovalPolicy.DESTROY)

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
            family="planetary-api-task",
        )

        # Note: ECR pull permissions are granted automatically by CDK
        # when using ContainerImage.from_ecr_repository()

        # Container definition — db.secret fields: username, password, host, dbname
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
                "DB_USER": ecs.Secret.from_secrets_manager(db.secret, "username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(db.secret, "password"),
                "DB_HOST": ecs.Secret.from_secrets_manager(db.secret, "host"),
                "DB_NAME": ecs.Secret.from_secrets_manager(db.secret, "dbname"),
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

        # Mailpit sidecar — captures emails sent by the app to localhost:1025
        mailpit = task_definition.add_container(
            "mailpit",
            image=ecs.ContainerImage.from_registry("axllent/mailpit"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="mailpit"),
            essential=False,
        )
        mailpit.add_port_mappings(
            ecs.PortMapping(container_port=1025),  # SMTP
            ecs.PortMapping(container_port=8025),  # HTTP UI
        )

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

        # Allow ECS tasks to connect to RDS on port 3306
        rds_sg.add_ingress_rule(
            peer=alb_service.service.connections.security_groups[0],
            connection=ec2.Port.tcp(3306),
            description="MySQL access from ECS tasks",
        )

        # Health check path
        alb_service.target_group.configure_health_check(
            path="/",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
        )

        self.service = alb_service.service
        self.alb_dns_name = alb_service.load_balancer.load_balancer_dns_name
        self.alb_sg_id = alb_service.load_balancer.connections.security_groups[
            0
        ].security_group_id
        self.task_def_family = "planetary-api-task"
        self.task_sg_id = alb_service.service.connections.security_groups[
            0
        ].security_group_id
        self.private_subnet_ids = [s.subnet_id for s in vpc.private_subnets]

        # Mailpit UI accessible on port 8025 of the ALB
        mailpit_listener = alb_service.load_balancer.add_listener(
            "MailpitListener",
            port=8025,
            protocol=elbv2.ApplicationProtocol.HTTP,
            open=True,
        )
        mailpit_listener.add_targets(
            "MailpitTargets",
            port=8025,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[
                alb_service.service.load_balancer_target(
                    container_name="mailpit",
                    container_port=8025,
                )
            ],
            health_check=elbv2.HealthCheck(
                path="/",
                healthy_http_codes="200",
                interval=Duration.seconds(30),
            ),
        )

        CfnOutput(self, "ServiceArn", value=self.service.service_arn)
        CfnOutput(self, "ClusterArn", value=self.cluster.cluster_arn)
        CfnOutput(
            self, "AlbDnsName", value=alb_service.load_balancer.load_balancer_dns_name
        )
        CfnOutput(
            self,
            "MailpitUrl",
            value=f"http://{alb_service.load_balancer.load_balancer_dns_name}:8025",
        )
