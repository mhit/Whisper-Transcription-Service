import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class WhisperTranscription implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Whisper Transcription',
		name: 'whisperTranscription',
		icon: 'file:whisper.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Japanese-optimized video/audio transcription using Whisper',
		defaults: {
			name: 'Whisper Transcription',
		},
		inputs: ['main'],
		outputs: ['main'],
		credentials: [
			{
				name: 'whisperTranscriptionApi',
				required: true,
			},
		],
		properties: [
			// Operation
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Create Job from URL',
						value: 'createFromUrl',
						description: 'Create a transcription job from a video URL',
						action: 'Create job from URL',
					},
					{
						name: 'Create Job from File',
						value: 'createFromFile',
						description: 'Create a transcription job from an uploaded file',
						action: 'Create job from file',
					},
					{
						name: 'Get Job Status',
						value: 'getStatus',
						description: 'Get the status of a transcription job',
						action: 'Get job status',
					},
					{
						name: 'Wait for Completion',
						value: 'waitForCompletion',
						description: 'Wait for a job to complete (with polling)',
						action: 'Wait for job completion',
					},
					{
						name: 'Download Result',
						value: 'downloadResult',
						description: 'Download the transcription result',
						action: 'Download result',
					},
					{
						name: 'Delete Job',
						value: 'deleteJob',
						description: 'Delete a transcription job',
						action: 'Delete job',
					},
				],
				default: 'createFromUrl',
			},

			// Create from URL fields
			{
				displayName: 'Video URL',
				name: 'url',
				type: 'string',
				default: '',
				placeholder: 'https://www.youtube.com/watch?v=...',
				description: 'URL of the video to transcribe (YouTube, Vimeo, etc.)',
				required: true,
				displayOptions: {
					show: {
						operation: ['createFromUrl'],
					},
				},
			},

			// Create from File fields
			{
				displayName: 'Binary Property',
				name: 'binaryPropertyName',
				type: 'string',
				default: 'data',
				description: 'Name of the binary property containing the file to upload',
				required: true,
				displayOptions: {
					show: {
						operation: ['createFromFile'],
					},
				},
			},

			// Job ID fields
			{
				displayName: 'Job ID',
				name: 'jobId',
				type: 'string',
				default: '',
				placeholder: 'JOB-ABC123',
				description: 'The job ID to query',
				required: true,
				displayOptions: {
					show: {
						operation: ['getStatus', 'waitForCompletion', 'downloadResult', 'deleteJob'],
					},
				},
			},

			// Wait for Completion options
			{
				displayName: 'Polling Interval (seconds)',
				name: 'pollingInterval',
				type: 'number',
				default: 10,
				description: 'How often to check the job status',
				displayOptions: {
					show: {
						operation: ['waitForCompletion'],
					},
				},
			},
			{
				displayName: 'Timeout (minutes)',
				name: 'timeout',
				type: 'number',
				default: 60,
				description: 'Maximum time to wait for completion',
				displayOptions: {
					show: {
						operation: ['waitForCompletion'],
					},
				},
			},

			// Download options
			{
				displayName: 'Output Format',
				name: 'outputFormat',
				type: 'options',
				options: [
					{ name: 'JSON', value: 'json' },
					{ name: 'Text', value: 'txt' },
					{ name: 'SRT Subtitles', value: 'srt' },
					{ name: 'Markdown', value: 'md' },
				],
				default: 'json',
				description: 'The format to download the transcription in',
				displayOptions: {
					show: {
						operation: ['downloadResult'],
					},
				},
			},

			// Additional options
			{
				displayName: 'Additional Options',
				name: 'additionalOptions',
				type: 'collection',
				placeholder: 'Add Option',
				default: {},
				displayOptions: {
					show: {
						operation: ['createFromUrl', 'createFromFile'],
					},
				},
				options: [
					{
						displayName: 'Webhook URL',
						name: 'webhookUrl',
						type: 'string',
						default: '',
						description: 'URL to receive notifications when the job completes',
					},
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const credentials = await this.getCredentials('whisperTranscriptionApi');
		const baseUrl = credentials.baseUrl as string;

		for (let i = 0; i < items.length; i++) {
			try {
				const operation = this.getNodeParameter('operation', i) as string;
				let response: any;

				switch (operation) {
					case 'createFromUrl': {
						const url = this.getNodeParameter('url', i) as string;
						const additionalOptions = this.getNodeParameter('additionalOptions', i) as {
							webhookUrl?: string;
						};

						const formData: Record<string, string> = { url };
						if (additionalOptions.webhookUrl) {
							formData.webhook_url = additionalOptions.webhookUrl;
						}

						response = await this.helpers.httpRequest({
							method: 'POST',
							url: `${baseUrl}/api/jobs`,
							body: formData,
							headers: {
								'Content-Type': 'application/x-www-form-urlencoded',
							},
						});
						break;
					}

					case 'createFromFile': {
						const binaryPropertyName = this.getNodeParameter('binaryPropertyName', i) as string;
						const additionalOptions = this.getNodeParameter('additionalOptions', i) as {
							webhookUrl?: string;
						};

						const binaryData = this.helpers.assertBinaryData(i, binaryPropertyName);
						const buffer = await this.helpers.getBinaryDataBuffer(i, binaryPropertyName);

						const formData: Record<string, any> = {
							file: {
								value: buffer,
								options: {
									filename: binaryData.fileName || 'upload.mp4',
									contentType: binaryData.mimeType || 'video/mp4',
								},
							},
						};

						if (additionalOptions.webhookUrl) {
							formData.webhook_url = additionalOptions.webhookUrl;
						}

						response = await this.helpers.httpRequest({
							method: 'POST',
							url: `${baseUrl}/api/jobs`,
							formData,
						});
						break;
					}

					case 'getStatus': {
						const jobId = this.getNodeParameter('jobId', i) as string;
						response = await this.helpers.httpRequest({
							method: 'GET',
							url: `${baseUrl}/api/jobs/${jobId}`,
						});
						break;
					}

					case 'waitForCompletion': {
						const jobId = this.getNodeParameter('jobId', i) as string;
						const pollingInterval = this.getNodeParameter('pollingInterval', i) as number;
						const timeout = this.getNodeParameter('timeout', i) as number;

						const startTime = Date.now();
						const timeoutMs = timeout * 60 * 1000;

						while (true) {
							response = await this.helpers.httpRequest({
								method: 'GET',
								url: `${baseUrl}/api/jobs/${jobId}`,
							});

							if (response.status === 'completed' || response.status === 'failed') {
								break;
							}

							if (Date.now() - startTime > timeoutMs) {
								throw new NodeOperationError(
									this.getNode(),
									`Timeout waiting for job ${jobId} to complete`,
								);
							}

							await new Promise((resolve) => setTimeout(resolve, pollingInterval * 1000));
						}
						break;
					}

					case 'downloadResult': {
						const jobId = this.getNodeParameter('jobId', i) as string;
						const outputFormat = this.getNodeParameter('outputFormat', i) as string;

						const fileResponse = await this.helpers.httpRequest({
							method: 'GET',
							url: `${baseUrl}/api/jobs/${jobId}/download`,
							qs: { format: outputFormat },
							encoding: 'arraybuffer',
							returnFullResponse: true,
						});

						const mimeTypes: Record<string, string> = {
							json: 'application/json',
							txt: 'text/plain',
							srt: 'text/plain',
							md: 'text/markdown',
						};

						const binaryData = await this.helpers.prepareBinaryData(
							Buffer.from(fileResponse.body as ArrayBuffer),
							`${jobId}.${outputFormat}`,
							mimeTypes[outputFormat],
						);

						response = {
							job_id: jobId,
							format: outputFormat,
							binary: { data: binaryData },
						};
						break;
					}

					case 'deleteJob': {
						const jobId = this.getNodeParameter('jobId', i) as string;
						await this.helpers.httpRequest({
							method: 'DELETE',
							url: `${baseUrl}/api/jobs/${jobId}`,
						});
						response = { success: true, job_id: jobId, message: 'Job deleted' };
						break;
					}

					default:
						throw new NodeOperationError(this.getNode(), `Unknown operation: ${operation}`);
				}

				// Handle binary data separately
				if (operation === 'downloadResult' && response.binary) {
					returnData.push({
						json: { job_id: response.job_id, format: response.format },
						binary: response.binary,
					});
				} else {
					returnData.push({ json: response });
				}

			} catch (error: any) {
				if (this.continueOnFail()) {
					returnData.push({
						json: {
							error: error.message,
						},
					});
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}
}
