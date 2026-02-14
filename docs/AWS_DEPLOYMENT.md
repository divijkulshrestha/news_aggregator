# AWS Deployment Guide

Complete guide for deploying the Personal News Aggregator on AWS infrastructure.

> 💡 **See Also:** [Project Implementation Plan](PROJECT_PLAN.md) for the complete roadmap from local development to production deployment.

## Architecture Overview

```mermaid
graph TB
    subgraph Internet
        User[User Browser]
    end
    
    subgraph AWS Cloud
        subgraph Compute
            EB[EventBridge<br/>Hourly Schedule]
            ECS1[ECS Fargate<br/>API Service]
            ECS2[ECS Task<br/>ETL Runner]
        end
        
        subgraph Storage
            ECR[ECR<br/>Container Registry]
            RDS[(RDS PostgreSQL<br/>Database)]
        end
        
        subgraph Optional
            ALB[Application<br/>Load Balancer]
            CF[CloudFront<br/>CDN]
        end
        
        subgraph Monitoring
            CW[CloudWatch<br/>Logs & Metrics]
        end
    end
    
    User -->|HTTPS| ALB
    ALB --> ECS1
    ECS1 -->|Read/Write| RDS
    
    EB -.Trigger.-> ECS2
    ECS2 -->|Fetch & Store| RDS
    
    ECS1 -->|Pull Image| ECR
    ECS2 -->|Pull Image| ECR
    
    ECS1 -->|Logs| CW
    ECS2 -->|Logs| CW
    RDS -->|Metrics| CW
    
    style RDS fill:#4CAF50
    style ECS1 fill:#2196F3
    style ECS2 fill:#FF9800
    style EB fill:#9C27B0
    style ECR fill:#00BCD4
    style CW fill:#FFC107
    style ALB fill:#E91E63
```

## Cost Estimate

### Free Tier Eligible (First 12 months)
- **RDS db.t3.micro**: 750 hours/month free
- **ECS Fargate**: 25 GB storage free
- **EventBridge**: 1M events/month free
- **Data Transfer**: 100 GB/month free

### After Free Tier (~$20-30/month)
- RDS db.t3.micro (20GB): ~$15/month
- ECS Fargate (0.25 vCPU, 0.5GB RAM): ~$10/month
- EventBridge: <$1/month
- Data Transfer: ~$1-5/month

## Prerequisites

- AWS Account
- AWS CLI installed and configured
- Docker Desktop (for local testing)
- Basic knowledge of AWS Console

## Deployment Workflow

```mermaid
flowchart TD
    Start([Start Deployment]) --> RDS[1. Create RDS PostgreSQL]
    RDS --> ECR[2. Create ECR Repository]
    ECR --> Build[3. Build Docker Image]
    Build --> Push[4. Push to ECR]
    Push --> Cluster[5. Create ECS Cluster]
    Cluster --> Task[6. Create Task Definitions]
    Task --> Service[7. Create ECS Service for API]
    Service --> EB[8. Setup EventBridge Schedule]
    EB --> Init[9. Run Initial ETL]
    Init --> Test[10. Test Application]
    Test --> Monitor[11. Setup Monitoring]
    Monitor --> End([Deployment Complete])
    
    style Start fill:#4CAF50
    style End fill:#4CAF50
    style RDS fill:#FF9800
    style Service fill:#2196F3
    style Test fill:#9C27B0
```

## Step-by-Step Deployment

### 1. Set Up RDS PostgreSQL Database

#### Create Database via AWS Console

1. **Navigate to RDS Console**
   - Go to AWS Console → RDS → Databases → Create database

2. **Engine Options**
   - Engine type: PostgreSQL
   - Version: PostgreSQL 16.x
   - Template: Free tier (or Production for better performance)

3. **Settings**
   - DB instance identifier: `news-aggregator-db`
   - Master username: `news_user`
   - Master password: Create a strong password (save it!)

4. **Instance Configuration**
   - DB instance class: `db.t3.micro` (free tier eligible)
   - Allocated storage: 20 GB
   - Storage autoscaling: Enable (max 100 GB)

5. **Connectivity**
   - VPC: Default VPC (or create new)
   - Public access: **Yes** (for now; restrict later)
   - VPC security group: Create new → `news-db-sg`
   - Availability Zone: No preference

6. **Database Authentication**
   - Password authentication

7. **Additional Configuration**
   - Initial database name: `news_db`
   - Backup retention: 7 days
   - Enable automatic minor version upgrade

8. **Create Database** (takes ~10 minutes)

9. **Note the Endpoint**
   - Navigate to your database → Connectivity & security
   - Copy the **Endpoint** (e.g., `news-aggregator-db.abc123.us-east-1.rds.amazonaws.com`)

#### Configure Security Group

1. **Edit Inbound Rules**
   - Go to EC2 → Security Groups → `news-db-sg`
   - Add rule:
     - Type: PostgreSQL
     - Protocol: TCP
     - Port: 5432
     - Source: `0.0.0.0/0` (⚠️ restrict this later to your ECS security group)

### 2. Build and Push Docker Image to ECR

#### Create ECR Repository

```bash
# Set your AWS region
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create ECR repository
aws ecr create-repository \
    --repository-name news-aggregator \
    --region $AWS_REGION
```

#### Build and Push Image

```bash
# Authenticate Docker with ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build the image
cd /path/to/news_etl
docker build -t news-aggregator .

# Tag the image
docker tag news-aggregator:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/news-aggregator:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/news-aggregator:latest
```

### 3. Create ECS Cluster

```bash
# Create ECS cluster
aws ecs create-cluster \
    --cluster-name news-aggregator-cluster \
    --region $AWS_REGION
```

Or via Console:
1. ECS → Clusters → Create Cluster
2. Cluster name: `news-aggregator-cluster`
3. Infrastructure: AWS Fargate (serverless)
4. Create

### 4. Create Task Execution Role

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://trust-policy.json

# Attach AWS managed policy
aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### 5. Create ECS Task Definitions

#### API Service Task Definition

Create `task-definition-api.json`:

```json
{
  "family": "news-aggregator-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/news-aggregator:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://news_user:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/news_db"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/news-aggregator-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

**Register task definition:**

```bash
# Create CloudWatch log group first
aws logs create-log-group --log-group-name /ecs/news-aggregator-api

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition-api.json
```

#### ETL Task Definition

Create `task-definition-etl.json`:

```json
{
  "family": "news-aggregator-etl",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "etl",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/news-aggregator:latest",
      "essential": true,
      "command": ["python", "scripts/run_etl.py"],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://news_user:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/news_db"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/news-aggregator-etl",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

**Register task definition:**

```bash
aws logs create-log-group --log-group-name /ecs/news-aggregator-etl
aws ecs register-task-definition --cli-input-json file://task-definition-etl.json
```

### 6. Create ECS Service for API

```bash
# Get your default VPC ID
export VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" --output text)

# Get subnet IDs
export SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

# Create security group for ECS tasks
export ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name news-ecs-sg \
    --description "Security group for news aggregator ECS tasks" \
    --vpc-id $VPC_ID \
    --query 'GroupId' --output text)

# Allow inbound traffic on port 8000
aws ec2 authorize-security-group-ingress \
    --group-id $ECS_SG_ID \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0

# Create ECS service
aws ecs create-service \
    --cluster news-aggregator-cluster \
    --service-name news-api-service \
    --task-definition news-aggregator-api \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}"
```

### 7. Set Up Scheduled ETL with EventBridge

#### Create EventBridge Rule (Console Method)

1. **Navigate to EventBridge**
   - AWS Console → EventBridge → Rules → Create rule

2. **Define Rule Details**
   - Name: `news-etl-hourly`
   - Description: Run news ETL every hour
   - Event bus: default
   - Rule type: Schedule

3. **Define Schedule**
   - Schedule pattern: Rate-based schedule
   - Rate expression: `rate(1 hour)`
   - Or use cron: `cron(0 * * * ? *)` (every hour at minute 0)

4. **Select Target**
   - Target types: AWS service
   - Select a target: ECS task
   - Cluster: `news-aggregator-cluster`
   - Task Definition: `news-aggregator-etl`
   - Launch type: FARGATE
   - Platform version: LATEST

5. **Network Configuration**
   - VPC: Default VPC
   - Subnets: Select your subnets
   - Security groups: `$ECS_SG_ID`
   - Auto-assign public IP: ENABLED

6. **Create Role**
   - Create a new role for this schedule

7. **Create Rule**

### 8. Initialize Database

Run ETL once manually to create tables and populate initial data:

```bash
# Run ETL task manually
aws ecs run-task \
    --cluster news-aggregator-cluster \
    --task-definition news-aggregator-etl \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}"
```

### 9. Access Your Application

#### Find Your API Public IP

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
    --cluster news-aggregator-cluster \
    --service-name news-api-service \
    --query 'taskArns[0]' --output text)

# Get ENI ID
ENI_ID=$(aws ecs describe-tasks \
    --cluster news-aggregator-cluster \
    --tasks $TASK_ARN \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
    --output text)

# Get public IP
aws ec2 describe-network-interfaces \
    --network-interface-ids $ENI_ID \
    --query 'NetworkInterfaces[0].Association.PublicIp' \
    --output text
```

Access your application at: `http://YOUR_PUBLIC_IP:8000`

## Optional: Add Application Load Balancer

For production, add an ALB for better availability and HTTPS support:

1. Create Application Load Balancer
2. Create Target Group (port 8000)
3. Update ECS Service to use ALB
4. Add ACM certificate for HTTPS
5. Update security groups

## Security Best Practices

### 1. Use Secrets Manager for Database Credentials

```bash
# Store database URL in Secrets Manager
aws secretsmanager create-secret \
    --name news-db-credentials \
    --secret-string '{"DATABASE_URL":"postgresql://news_user:PASSWORD@ENDPOINT:5432/news_db"}'

# Update task definition to reference secret instead of plaintext
```

### 2. Restrict Database Access

Update RDS security group to only allow access from ECS security group:

```bash
aws ec2 revoke-security-group-ingress \
    --group-id $DB_SG_ID \
    --protocol tcp \
    --port 5432 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id $DB_SG_ID \
    --protocol tcp \
    --port 5432 \
    --source-group $ECS_SG_ID
```

### 3. Use VPC Endpoints

Avoid internet traffic for AWS services (ECR, CloudWatch, etc.)

### 4. Enable Encryption

- RDS: Enable encryption at rest
- Enable encryption in transit (SSL/TLS)

## Monitoring and Logging

### CloudWatch Logs

View logs:
- API logs: `/ecs/news-aggregator-api`
- ETL logs: `/ecs/news-aggregator-etl`

### CloudWatch Alarms

Create alarms for:
- RDS CPU > 80%
- ECS task failures
- ETL job failures

### Monitoring Dashboard

Create CloudWatch dashboard with:
- RDS metrics
- ECS service metrics
- API latency
- ETL success rate

## Troubleshooting

### API Service Not Starting

```bash
# Check task logs
aws logs tail /ecs/news-aggregator-api --follow

# Check task status
aws ecs describe-tasks \
    --cluster news-aggregator-cluster \
    --tasks $TASK_ARN
```

### Database Connection Issues

- Verify security group allows traffic from ECS
- Check DATABASE_URL format
- Ensure RDS is in same VPC

### ETL Job Failing

```bash
# Check ETL logs
aws logs tail /ecs/news-aggregator-etl --follow

# Run task manually for debugging
aws ecs run-task \
    --cluster news-aggregator-cluster \
    --task-definition news-aggregator-etl \
    --launch-type FARGATE \
    --network-configuration "..."
```

## Cost Optimization

1. **Use Spot Instances** for ETL tasks (up to 70% savings)
2. **Stop/Start RDS** during development (save ~$360/year)
3. **Use Aurora Serverless** for variable workloads
4. **Enable S3 logs lifecycle** to expire old logs
5. **Set billing alerts** on CloudWatch

## Updating the Application

```bash
# Build and push new image
docker build -t news-aggregator .
docker tag news-aggregator:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/news-aggregator:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/news-aggregator:latest

# Update ECS service (triggers rolling deployment)
aws ecs update-service \
    --cluster news-aggregator-cluster \
    --service news-api-service \
    --force-new-deployment
```

## Cleanup

To avoid charges, delete resources when done:

```bash
# Delete ECS service
aws ecs delete-service \
    --cluster news-aggregator-cluster \
    --service news-api-service \
    --force

# Delete ECS cluster
aws ecs delete-cluster --cluster news-aggregator-cluster

# Delete RDS instance
aws rds delete-db-instance \
    --db-instance-identifier news-aggregator-db \
    --skip-final-snapshot

# Delete ECR repository
aws ecr delete-repository \
    --repository-name news-aggregator \
    --force

# Delete security groups, log groups, etc.
```

## Next Steps

- Set up custom domain with Route 53
- Add HTTPS with ALB + ACM
- Implement CI/CD with GitHub Actions or CodePipeline
- Add monitoring with Grafana
- Implement caching with ElastiCache

## Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS RDS Documentation](https://docs.aws.amazon.com/rds/)
- [AWS EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
- [AWS Free Tier Details](https://aws.amazon.com/free/)
