import { Queue, Worker, Job } from 'bullmq';
import IORedis from 'ioredis';
import { safeErrorType } from '../policy.js';

const redisBaseOptions = {
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT || '6379', 10),
  password: process.env.REDIS_PASSWORD || undefined,
  connectTimeout: 5000,
  retryStrategy: (attempt: number) => Math.min(attempt * 100, 1000),
};

const producerConnection = new IORedis({
  ...redisBaseOptions,
  maxRetriesPerRequest: 2,
  enableOfflineQueue: false,
});
const workerConnections = new Set<IORedis>();

export const goofishCrawlQueue = new Queue('goofish-crawl', {
  connection: producerConnection,
  defaultJobOptions: {
    attempts: 2,
    backoff: {
      type: 'exponential',
      delay: 30000,
    },
    removeOnComplete: true,
    removeOnFail: true,
  },
});

export function createWorker(processor: (job: Job) => Promise<void>): Worker {
  const workerConnection = new IORedis({
    ...redisBaseOptions,
    maxRetriesPerRequest: null,
  });
  workerConnections.add(workerConnection);
  const worker = new Worker('goofish-crawl', processor, {
    connection: workerConnection,
    concurrency: 1,
  });

  worker.on('completed', (job) => {
    console.log(`[Worker] 任务完成: jobId=${job.id}`);
  });

  worker.on('failed', (job, err) => {
    console.error(`[Worker] 任务失败: jobId=${job?.id}, errorType=${safeErrorType(err)}`);
  });

  worker.on('error', (error) => {
    console.error(`[Worker] operation=queue errorType=${safeErrorType(error)}`);
  });
  worker.on('closed', () => workerConnections.delete(workerConnection));

  return worker;
}

export async function closeQueue(): Promise<void> {
  await Promise.race([
    goofishCrawlQueue.close(),
    new Promise((resolve) => setTimeout(resolve, 5000)),
  ]);
  producerConnection.disconnect(false);
  for (const connection of workerConnections) connection.disconnect(false);
  workerConnections.clear();
}
