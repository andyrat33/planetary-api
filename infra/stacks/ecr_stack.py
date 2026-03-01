from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ecr as ecr,
    CfnOutput,
)
from constructs import Construct


class EcrStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.repo = ecr.Repository(
            self,
            "PlanetaryApiRepo",
            repository_name="planetary-api",
            removal_policy=RemovalPolicy.RETAIN,
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    max_image_count=10,
                    description="Keep last 10 images",
                )
            ],
        )

        CfnOutput(self, "RepoUri", value=self.repo.repository_uri)
        CfnOutput(self, "RepoArn", value=self.repo.repository_arn)
