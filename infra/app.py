#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.ecr_stack import EcrStack
from stacks.ecs_stack import EcsStack
from stacks.pipeline_stack import PipelineStack

app = cdk.App()

ecr_stack = EcrStack(
    app,
    "PlanetaryEcr",
    env=cdk.Environment(
        account="450372565572",
        region="us-east-1",
    ),
)

ecs_stack = EcsStack(
    app,
    "PlanetaryEcs",
    ecr_repo=ecr_stack.repo,
    env=cdk.Environment(
        account="450372565572",
        region="us-east-1",
    ),
)

pipeline_stack = PipelineStack(
    app,
    "PlanetaryPipeline",
    ecr_repo=ecr_stack.repo,
    ecs_service=ecs_stack.service,
    ecs_cluster=ecs_stack.cluster,
    alb_dns_name=ecs_stack.alb_dns_name,
    alb_sg_id=ecs_stack.alb_sg_id,
    env=cdk.Environment(
        account="450372565572",
        region="us-east-1",
    ),
)

pipeline_stack.add_dependency(ecr_stack)
pipeline_stack.add_dependency(ecs_stack)

app.synth()
