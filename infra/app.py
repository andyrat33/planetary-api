#!/usr/bin/env python3
import aws_cdk as cdk

from config import ACCOUNT, REGION
from stacks.ecr_stack import EcrStack
from stacks.ecs_stack import EcsStack
from stacks.pipeline_stack import PipelineStack

app = cdk.App()

ecr_stack = EcrStack(
    app,
    "PlanetaryEcr",
    env=cdk.Environment(
        account=ACCOUNT,
        region=REGION,
    ),
)

ecs_stack = EcsStack(
    app,
    "PlanetaryEcs",
    ecr_repo=ecr_stack.repo,
    env=cdk.Environment(
        account=ACCOUNT,
        region=REGION,
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
    task_def_family=ecs_stack.task_def_family,
    task_sg_id=ecs_stack.task_sg_id,
    private_subnet_ids=ecs_stack.private_subnet_ids,
    env=cdk.Environment(
        account=ACCOUNT,
        region=REGION,
    ),
)

pipeline_stack.add_dependency(ecr_stack)
pipeline_stack.add_dependency(ecs_stack)

app.synth()
