<script lang="ts">
    import { tick } from 'svelte';
    import Self from './CommentItem.svelte';
    
    export interface Comment { // comment type that section and main page receive
        id: string;
        author: string;
        content: string;
        articleId: string;
        removed: boolean;
        removedBy: string;
        timestamp?: number;
        parentId?: string | null;
    }

    export interface CommentItemProps { // props that parents change
        comment: Comment;
        allComments: Comment[];
        onReply: (commentId: string) => void;
        onPostReply: (detail: { content: string; parentId: string }) => void;
        currentArticleId: string;
        level?: number;
    }
	
    // prop i.e export the variables
    let { comment, allComments, onReply, onPostReply, currentArticleId, level = 0 }: CommentItemProps = $props();
	
    // --- Reply States ---
    let showReplyInput = $state(false);
    let replyContent = $state('');
    let replyInputRef: HTMLTextAreaElement | null = $state(null);
    const replies = $derived(
        allComments.filter(c => c.parentId === comment.id)
            .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
    );
	
    // --- Get Comment Author Function ---
    function getInitials(name: string): string {
        // TEMP - Anon -- replace with author from OAuth
        if (!name || name.trim() === "TEMP - Anon" || name.trim() === "") return 'A';
        const parts = name.split(' ').filter(p => p.length > 0);
        if (parts.length === 0) return '?';
        if (parts.length > 1) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return parts[0][0].toUpperCase();
    }
	
    // --- Reply Focus Function ---
    function handleReplyClick() {
        showReplyInput = !showReplyInput;
        if (showReplyInput) {
            // possibly notify parent here?
            tick().then(() => {
                replyInputRef?.focus();
            });
        } else {
            replyContent = '';
        }
    }
	
    // --- Reply Submit/Post to Parent --
    function handlePostReplySubmit() {
        if (!replyContent.trim()) return;
        onPostReply({ content: replyContent, parentId: comment.id });
        replyContent = '';
        showReplyInput = false;
    }
	
    // --- Reply Input-Area Resize Function ---
    function autoResizeReplyTextarea(event: Event) {
        const textarea = event.target as HTMLTextAreaElement;
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    }
	
    // TODO: Moderation
    function handleDeleteClick() {
        console.log('Delete placeholder for', comment.id, '.');
    }

</script>

<div class="comment-item" style="--indent-level: {level};">
		{#if level > 0}
				<div class="indent-line"></div> <!-- DIVIDER -->
		{/if}
		<div class="comment-content-wrapper">
				<div class="comment-main">
						<div class="profile-picture">
								<span>{getInitials(comment.author)}</span>
						</div>
						<div class="comment-body">
								<div class="comment-header">
								<!-- COMMENTER NAME AND TIMESTAMP -->
										<span class="comment-author-name">{comment.author}</span>
										{#if comment.timestamp}
												<span class="comment-timestamp">
													- {new Date(comment.timestamp * 1000).toLocaleDateString()}
												</span>
										{/if}
								</div>
								<!-- INPUT BOX -->
								<p class="comment-text">
										{#if comment.removed}
												<s class="removed-comment-content">{comment.content}</s>
												<br />
												<em class="removed-comment-by">(Comment removed by {comment.removedBy || 'moderator'})</em>
										{:else}
												{comment.content}
										{/if}
								</p>
								<!-- REPLY/DELETE BUTTONS -->
								<div class="comment-actions">
										<button class="action-button reply-button" onclick={handleReplyClick}>Reply</button>
										<button class="action-button delete-button" onclick={handleDeleteClick}>Delete</button>
								</div>
						</div>
				</div>
				{#if showReplyInput}
						<div class="reply-input-area">
								<!-- INPUT REPLY BOX -->
								<textarea
										bind:this={replyInputRef}
										bind:value={replyContent}
										placeholder="Write your reply..."
										rows="1"
										class="reply-textarea"
										oninput={autoResizeReplyTextarea}
								></textarea>
								<!-- POST/CANCEL BUTTONS -->
								<div class="reply-input-actions">
										<button class="action-button post-reply-button" onclick={handlePostReplySubmit} disabled={!replyContent.trim()}>Post Reply</button>
										<button class="action-button cancel-reply-button" onclick={() => { showReplyInput = false; replyContent = ''; }}>Cancel</button>
								</div>
						</div>
				{/if}
				
				
				{#if replies.length > 0}
						<div class="comment-replies">
								<!-- RECURSIVE CALL FOR THREADING TODO: implement max or continue thread option -->
								{#each replies as reply (reply.id)}
										<Self
												comment={reply}
												{allComments}
												{onReply}
												{onPostReply}
												{currentArticleId}
												level={level + 1}
										/>
								{/each}
						</div>
				{/if}
		</div>
</div>
{#if level === 0}
		<hr class="comment-separator" />
{/if}

<style>
    .comment-item {
        display: flex;
        position: relative;
        padding-left: calc(var(--indent-level, 0) * 30px);
        margin-bottom: 0;
    }

    .indent-line {
        position: absolute;
        left: calc(var(--indent-level, 0) * 30px - 15px);
        top: 25px;
        bottom: 10px;
        width: 2px;
        background-color: #e0e0e0;
    }

    .comment-content-wrapper {
        display: flex;
        flex-direction: column;
        width: 100%;
        padding-bottom: 10px;
    }

    .comment-main {
        display: flex;
        gap: 12px;
        width: 100%;
    }

    .profile-picture {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #ccc;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.1em;
        flex-shrink: 0;
        margin-top: 2px;
    }

    .comment-body {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }

    .comment-header {
        display: flex;
        align-items: baseline;
        margin-bottom: 4px;
    }

    .comment-author-name {
        font-weight: bold;
        font-size: 0.95em;
        color: #333;
    }

    .comment-timestamp {
        font-size: 0.8em;
        color: #777;
        margin-left: 8px;
    }

    .comment-text {
        font-size: 0.9em;
        line-height: 1.5;
        white-space: pre-wrap;
        word-wrap: break-word;
        margin: 0 0 8px 0;
        color: #444;
    }
    .removed-comment-content { color: #888; }
    .removed-comment-by { color: #888; font-size: 0.9em; }

    .comment-actions {
        display: flex;
        gap: 10px;
        align-items: center;
        margin-top: 4px;
    }

    .action-button {
        background-color: transparent;
        border: none;
        color: #007bff;
        cursor: pointer;
        padding: 4px 0;
        font-size: 0.8em;
        font-weight: 500;
    }
    .action-button:hover {
        text-decoration: underline;
    }
    .delete-button {
        color: #dc3545;
    }
    .post-reply-button {
        background-color: #007bff;
        color: white;
        padding: 6px 10px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .post-reply-button:disabled {
        background-color: #cccccc;
        cursor: not-allowed;
    }
    .cancel-reply-button {
        color: #6c757d;
        padding: 6px 10px;
        font-size: 0.85em;
    }

    .reply-input-area {
        margin-top: 10px;
        padding-left: 52px; /* profile pic width + gap */
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .reply-textarea {
        width: 100%;
        padding: 8px 10px;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-size: 0.9em;
        line-height: 1.4;
        resize: none;
        overflow-y: hidden;
        min-height: 38px;
        box-sizing: border-box;
    }
    .reply-input-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
    }

    .comment-replies {
        margin-top: 10px;
    }

    .comment-separator {
        border: none;
        border-top: 1px solid #eaeaea;
        margin: 0;
    }
</style>