import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { Duration } from 'aws-cdk-lib';
import { Function, Code, Runtime } from 'aws-cdk-lib/aws-lambda';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { EventType, Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { LambdaDestination }  from 'aws-cdk-lib/aws-s3-notifications';
import { Role, ServicePrincipal, ManagedPolicy, PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import path = require("path");

export class HelloCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for video storage
    const s3Bucket = new Bucket(this, 'RecordingStorageBucketName', {
      bucketName: `recording-storage-${this.account}`,
      encryption: BucketEncryption.S3_MANAGED,
      versioned: true,
    });

    // IAM role and lambda
    const lambdaRole = new Role(this, 'RecordingProcessLambdaRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
    });
    lambdaRole.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName(
        'service-role/AWSLambdaBasicExecutionRole'));
    const lambdaRoleManagedPolicy = new ManagedPolicy(this, 'RecordingProcessLambdaRolePolicy', {
      managedPolicyName: 'RecordingProcessLambdaRolePolicy',
      description: 'customer Managed Policy for Recording processing Lambda',
      roles: [lambdaRole],
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            "s3:*",
          ],
          resources: [
            `${s3Bucket.bucketArn}/*`,
            s3Bucket.bucketArn,
          ]
        }),
        new PolicyStatement({
          sid: "TranscribeAccess",
          effect: Effect.ALLOW,
          actions: [
            'transcribe:*',
          ],
          resources: ["*"]
        }),
        new PolicyStatement({
          sid: "BedrockAccess",
          effect: Effect.ALLOW,
          actions: [
            'bedrock:*',
          ],
          resources: ["*"]
        })
      ]
    });
    const recordingProcessLambda = new Function(this, "RecordingProcessLambda", {
      code: Code.fromAsset(path.join('lib', 'lambda')),
      handler: "index.lambda_handler",
      environment: {
        'RecordingStorageBucketName': s3Bucket.bucketName,
      },
      runtime: Runtime.PYTHON_3_12,
      description: 'Lambda function to process recordings',
      role: lambdaRole,
      timeout: Duration.minutes(15),
      memorySize: 512,
      logRetention: RetentionDays.ONE_MONTH,
    });
    recordingProcessLambda.node.addDependency(lambdaRole);

    // add notification invocation
    s3Bucket.addEventNotification(
        EventType.OBJECT_CREATED,
        new LambdaDestination(recordingProcessLambda), {
          prefix: "video/",
        }
    );
  }
}
