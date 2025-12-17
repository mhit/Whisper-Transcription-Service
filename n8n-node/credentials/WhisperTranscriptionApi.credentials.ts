import {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class WhisperTranscriptionApi implements ICredentialType {
	name = 'whisperTranscriptionApi';
	displayName = 'Whisper Transcription API';
	documentationUrl = 'https://github.com/your-repo/whisper-transcription-service';

	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://localhost:8000',
			placeholder: 'http://localhost:8000',
			description: 'The base URL of your Whisper Transcription Service',
			required: true,
		},
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			description: 'Optional API key for authentication (leave empty if not required)',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				'X-API-Key': '={{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/api/health',
			method: 'GET',
		},
	};
}
