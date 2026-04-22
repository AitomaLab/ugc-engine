'use client';

import React, {useEffect, useRef} from 'react';

export type VideoEditorChatMessage = {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	timestamp?: Date;
};

export type VideoEditorChatSuggestion = {
	id: string;
	text: string;
	icon?: string;
};

const SuggestionIcon: React.FC<{id: string}> = ({id}) => {
	if (id === '1') {
		return (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden
			>
				<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
				<path d="M14 2v6h6" />
				<path d="M16 13H8" />
				<path d="M16 17H8" />
				<path d="M10 9H8" />
			</svg>
		);
	}
	if (id === '2') {
		return (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden
			>
				<line x1="4" x2="4" y1="21" y2="14" />
				<line x1="4" x2="4" y1="10" y2="3" />
				<line x1="12" x2="12" y1="21" y2="12" />
				<line x1="12" x2="12" y1="8" y2="3" />
				<line x1="20" x2="20" y1="21" y2="16" />
				<line x1="20" x2="20" y1="12" y2="3" />
				<line x1="1" x2="7" y1="14" y2="14" />
				<line x1="9" x2="15" y1="8" y2="8" />
				<line x1="17" x2="23" y1="16" y2="16" />
			</svg>
		);
	}
	if (id === '4') {
		return (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden
			>
				<path d="M9 18V5l12-2v13" />
				<circle cx="6" cy="18" r="3" />
				<circle cx="18" cy="16" r="3" />
			</svg>
		);
	}
	if (id === '5') {
		return (
			<svg
				xmlns="http://www.w3.org/2000/svg"
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden
			>
				<path d="M7 9v6" />
				<path d="M17 9v6" />
				<path d="M4 9a3 3 0 1 1 0 6" />
				<path d="M20 9a3 3 0 1 1 0 6" />
				<path d="M7 7h10" />
				<path d="M7 17h10" />
			</svg>
		);
	}
	return (
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			strokeLinecap="round"
			strokeLinejoin="round"
			aria-hidden
		>
			<circle cx="12" cy="13" r="8" />
			<path d="M12 9v4l2 2" />
			<path d="M5 3 2 6" />
			<path d="m22 6-3-3" />
		</svg>
	);
};

export const VideoEditorChat: React.FC<{
	messages: VideoEditorChatMessage[];
	inputValue: string;
	isLoading: boolean;
	suggestions: VideoEditorChatSuggestion[];
	onInputChange: (value: string) => void;
	onSend: () => void;
	onClearChat: () => void;
	onClose: () => void;
	onSuggestionClick: (text: string) => void;
	renderAssistantExtras?: (message: VideoEditorChatMessage) => React.ReactNode;
}> = ({
	messages,
	inputValue,
	isLoading,
	suggestions,
	onInputChange,
	onSend,
	onClearChat,
	onClose,
	onSuggestionClick,
	renderAssistantExtras,
}) => {
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const contentRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (contentRef.current) {
			contentRef.current.scrollTop = contentRef.current.scrollHeight;
		}
	}, [messages, isLoading]);

	useEffect(() => {
		if (textareaRef.current) {
			textareaRef.current.style.height = 'auto';
			const nextHeight = Math.min(textareaRef.current.scrollHeight, 200);
			textareaRef.current.style.height = `${nextHeight}px`;
		}
	}, [inputValue]);

	return (
		<div className="video-editor-chat">
			<header className="chat-header">
				<div className="header-content">
					<h2 className="header-title">Assistant</h2>
					<p className="header-subtitle">Timeline-aware help and quick edits</p>
				</div>
				<button
					onClick={onClose}
					className="close-button"
					aria-label="Close chat"
					type="button"
				>
					×
				</button>
			</header>

			<div ref={contentRef} className="chat-content">
				{messages.length === 0 ? (
					<div className="empty-state">
						<div className="suggestions-container">
							<h3 className="suggestions-title">TRY ASKING THINGS LIKE</h3>
							<div className="suggestions-grid">
								{suggestions.map((suggestion) => (
									<button
										key={suggestion.id}
										onClick={() => onSuggestionClick(suggestion.text)}
										className="suggestion-card"
										type="button"
									>
										<div className="suggestion-icon">
											<SuggestionIcon id={suggestion.id} />
										</div>
										<p className="suggestion-text">{suggestion.text}</p>
									</button>
								))}
							</div>
							<p className="helper-text">
								When edits are suggested, review the planned changes, then{' '}
								<span className="highlight">Approve</span> and apply.
							</p>
						</div>
					</div>
				) : (
					<div className="messages-container">
						{messages.map((message) => (
							<div
								key={message.id}
								className={`message-wrapper message-${message.role}`}
							>
								<div className="message-bubble">
									<p className="message-text">{message.content}</p>
									{message.timestamp ? (
										<span className="message-timestamp">
											{message.timestamp.toLocaleTimeString([], {
												hour: '2-digit',
												minute: '2-digit',
											})}
										</span>
									) : null}
									{message.role === 'assistant' && renderAssistantExtras
										? renderAssistantExtras(message)
										: null}
								</div>
							</div>
						))}
						{isLoading ? (
							<div className="message-wrapper message-assistant">
								<div className="message-bubble loading-bubble">Thinking...</div>
							</div>
						) : null}
					</div>
				)}
			</div>

			<div className="section-divider" />

			<div className="chat-input-section">
				<label className="input-label">YOUR PROMPT</label>
				<div className="textarea-container">
					<textarea
						ref={textareaRef}
						value={inputValue}
						onChange={(e) => onInputChange(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === 'Enter' && !e.shiftKey) {
								e.preventDefault();
								onSend();
							}
						}}
						placeholder="Describe what you want to change..."
						className="chat-textarea"
						disabled={isLoading}
						rows={3}
					/>
					<button
						onClick={onSend}
						disabled={!inputValue.trim() || isLoading}
						className="send-button"
						aria-label="Send message"
						title="Send (Enter)"
						type="button"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="16"
							height="16"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="2.25"
							strokeLinecap="round"
							strokeLinejoin="round"
							aria-hidden
						>
							<path d="M5 12h14" />
							<path d="m13 6 6 6-6 6" />
						</svg>
					</button>
				</div>
				<p className="keyboard-hint">Enter to send · Shift + Enter for new line</p>
				<button onClick={onClearChat} className="clear-chat-button" type="button">
					Clear chat
				</button>
			</div>

			<style jsx>{`
				.video-editor-chat {
					display: flex;
					flex-direction: column;
					height: 100%;
					background: #111111;
					color: #ffffff;
					font-family: system-ui, -apple-system, Inter, Geist, 'Segoe UI', Roboto,
						sans-serif;
					border-radius: 12px;
					border: 1px solid #222222;
					overflow: hidden;
				}
				.chat-header {
					display: flex;
					justify-content: space-between;
					align-items: flex-start;
					padding: 20px 20px 16px 20px;
					border-bottom: 1px solid #222222;
				}
				.header-content {
					flex: 1;
					min-width: 0;
				}
				.header-title {
					margin: 0;
					font-size: 18px;
					font-weight: 700;
					color: #ffffff;
				}
				.header-subtitle {
					margin: 4px 0 0 0;
					font-size: 13px;
					font-weight: 400;
					color: #888888;
				}
				.close-button {
					background: none;
					border: none;
					padding: 0;
					color: #555555;
					cursor: pointer;
					font-size: 22px;
					line-height: 1;
					transition: color 150ms ease-out;
				}
				.close-button:hover {
					color: #aaaaaa;
				}
				.chat-content {
					flex: 1;
					overflow-y: auto;
					padding: 24px 20px;
				}
				.empty-state {
					width: 100%;
				}
				.suggestions-title {
					margin: 0 0 16px 0;
					font-size: 11px;
					color: #555555;
					letter-spacing: 0.12em;
					text-transform: uppercase;
					text-align: center;
					font-weight: 400;
				}
				.suggestions-grid {
					display: grid;
					grid-template-columns: 1fr;
					gap: 10px;
				}
				.suggestion-card {
					background: #1c1c1c;
					border: 1px solid #2a2a2a;
					border-radius: 10px;
					padding: 14px 16px;
					display: flex;
					align-items: center;
					gap: 12px;
					text-align: left;
					color: inherit;
					cursor: pointer;
					transition: background-color 150ms ease-out, border-color 150ms ease-out;
				}
				.suggestion-card:hover {
					background: #222222;
					border-color: #333333;
				}
				.suggestion-icon {
					width: 36px;
					height: 36px;
					background: #252525;
					border-radius: 8px;
					display: inline-flex;
					align-items: center;
					justify-content: center;
					flex-shrink: 0;
					color: #888888;
				}
				.suggestion-text {
					margin: 0;
					font-size: 14px;
					font-weight: 400;
					color: #ffffff;
				}
				.helper-text {
					margin: 16px 0 0 0;
					font-size: 13px;
					color: #666666;
					text-align: center;
					line-height: 1.5;
				}
				.highlight {
					color: #4a7cf6;
				}
				.messages-container {
					display: flex;
					flex-direction: column;
					gap: 12px;
				}
				.message-wrapper {
					display: flex;
				}
				.message-user {
					justify-content: flex-end;
				}
				.message-assistant {
					justify-content: flex-start;
				}
				.message-bubble {
					max-width: 88%;
					padding: 12px 14px;
					background: #1c1c1c;
					border: 1px solid #2a2a2a;
					border-radius: 10px;
					font-size: 14px;
				}
				.message-text {
					margin: 0;
					color: #ffffff;
					white-space: pre-wrap;
					line-height: 1.5;
				}
				.message-timestamp {
					display: block;
					margin-top: 6px;
					font-size: 11px;
					color: #666666;
				}
				.loading-bubble {
					color: #666666;
				}
				.section-divider {
					border-top: 1px solid #222222;
					width: 100%;
				}
				.chat-input-section {
					padding: 16px 20px 16px 20px;
				}
				.input-label {
					display: block;
					font-size: 11px;
					color: #444444;
					letter-spacing: 0.1em;
					text-transform: uppercase;
					margin-bottom: 8px;
				}
				.textarea-container {
					position: relative;
				}
				.chat-textarea {
					width: 100%;
					background: #161616;
					border: 1px solid #2a2a2a;
					border-radius: 10px;
					padding: 12px 14px;
					padding-right: 56px;
					min-height: 100px;
					max-height: 200px;
					resize: none;
					font-size: 14px;
					color: #ffffff;
					font-family: inherit;
					outline: none;
				}
				.chat-textarea::placeholder {
					color: #555555;
				}
				.chat-textarea:focus {
					border-color: #3a3a3a;
				}
				.send-button {
					position: absolute;
					bottom: 10px;
					right: 10px;
					width: 36px;
					height: 36px;
					border-radius: 9999px;
					border: none;
					background: #2c5ee8;
					color: #ffffff;
					display: inline-flex;
					align-items: center;
					justify-content: center;
					cursor: pointer;
					transition: background-color 150ms ease-out;
				}
				.send-button:hover:not(:disabled) {
					background: #3a6ef8;
				}
				.send-button:disabled {
					opacity: 0.45;
					cursor: not-allowed;
				}
				.keyboard-hint {
					margin: 8px 0 0 0;
					font-size: 11px;
					color: #444444;
				}
				.clear-chat-button {
					margin-top: 8px;
					padding-bottom: 16px;
					width: 100%;
					text-align: center;
					background: none;
					border: none;
					font-size: 13px;
					color: #555555;
					cursor: pointer;
					transition: color 150ms ease-out;
				}
				.clear-chat-button:hover {
					color: #aaaaaa;
				}
			`}</style>
		</div>
	);
};
