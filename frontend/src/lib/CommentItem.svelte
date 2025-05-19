<script lang="ts" >
    import {tick} from 'svelte';
    import Self from './CommentItem.svelte';
    import { userStore } from '$lib/stores/userStore.svelte';
    import type { User } from '$lib/stores/userStore.svelte';

    export interface Comment { // comment type that section and main page receive
        id: string;
        author: string;
        content: string;
        articleId: string;
        removed: boolean;
        removedBy: string;
        timestamp?: number;
        parentId?: string | null;
        moderationTimestamp?: number;
    }

    export interface CommentItemProps { // props that parents change
        comment: Comment;
        allComments: Comment[];
        onReply: (commentId: string) => void;
        onPostReply: (detail: { content: string; parentId: string }) => void;
        onModerateComment:
	        (detail: {
                commentId: string;
                action: 'delete_full' | 'redact_partial'; newContent?: string
            }) => Promise<boolean>;
        currentArticleId: string;
        level?: number;
    }
	
    // prop i.e export the variables
    let { comment, allComments, onReply, onPostReply, onModerateComment, currentArticleId, level = 0 }: CommentItemProps = $props();

    const FULL_BLOCK_CHAR = '\u2588'; // EC full block char

    let currentUserRole = $state<string | undefined>(undefined);
    let rawUserFromStore = $state<User | null>(null);
    $effect(() => {
        console.log('[CommentItem] Subscribing to userStore');
        return userStore.subscribe(user => {
            console.log('[CommentItem] userStore emitted:', user);
            rawUserFromStore = user;
            currentUserRole = user?.role;
            console.log('[CommentItem] currentUserRole set to:', currentUserRole);
        });
    });

    const canModerate = $derived(currentUserRole === 'admin' || currentUserRole === 'moderator');
    $effect(() => {
        console.log('[CommentItem] canModerate derived value:', canModerate, 'based on currentUserRole:', currentUserRole);
        console.log('[CommentItem] rawUserFromStore for debugging:', rawUserFromStore);
    });
    
    // --- Reply States ---
    let showReplyInput = $state(false);
    let replyContent = $state('');
    let replyInputRef: HTMLTextAreaElement | null = $state(null);
    const replies = $derived(
        allComments.filter(c => c.parentId === comment.id)
            .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
    );

    // --- NEW: Moderation States ---
    let showModerationOptions = $state(false);
    let isRedacting = $state(false);
    let editableCommentContent = $state(comment.content); // redact
    let commentTextRef: HTMLParagraphElement | null = $state(null); // edit text ref
    
    
    // --- Get Comment Author Function ---
    function getInitials(name: string): string {
        if (!name || name.trim() === "Anon" || name.trim() === "") return 'A';
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
        isRedacting = false;
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
    
    // --- Moderation Functions ---
    function toggleModerationOptions() {
        showModerationOptions = !showModerationOptions;
        isRedacting = false;
        if (!showModerationOptions) {
            if (commentTextRef) commentTextRef.contentEditable = 'false';
            editableCommentContent = comment.content;
        }
    }

    async function handleFullDelete() {
        if (confirm('Are you sure? This is not reversible.')) {
            const success = await onModerateComment({ commentId: comment.id, action: 'delete_full' });
            if (success) {
                showModerationOptions = false;
                isRedacting = false;
            } else {
                alert('Failed to delete comment. Try again.');
            }
        }
    }

    function startRedaction() {
        isRedacting = true;
        showModerationOptions = false; // hide options on init
        editableCommentContent = comment.content; // fill w/ current content
        tick().then(() => {
            if (commentTextRef) {
                commentTextRef.contentEditable = 'true';
                commentTextRef.focus();
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(commentTextRef);
                selection?.removeAllRanges();
                selection?.addRange(range);
            }
        });
    }

    function handleEditableContentInput() {
        if (commentTextRef) {
            editableCommentContent = commentTextRef.innerText; // innerText for plain text
        }
    }

    // Block Char Insert Helper
    function insertBlockCharsAtSelection() {
        if (isRedacting && commentTextRef) {
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const blockText = FULL_BLOCK_CHAR.repeat(range.toString().length || 1); // match selection length
                document.execCommand('insertText', false, blockText); // deprecated
                handleEditableContentInput(); // update state
            } else {
                alert("Please select text within the comment to redact.");
            }
        }
    }


    async function saveRedaction() {
        if (commentTextRef) {
            commentTextRef.contentEditable = 'false';
        }
        if (editableCommentContent === comment.content) {
            alert("No changes made to the comment.");
            isRedacting = false;
            return;
        }
        if (confirm('Are you sure you want to save these redactions?')) {
            const success = await onModerateComment({
                commentId: comment.id,
                action: 'redact_partial',
                newContent: editableCommentContent
            });
            if (success) {
                isRedacting = false;
            } else {
                alert('Failed to save redactions. Please try again.');
            }
        }
    }

    function cancelRedaction() {
        if (commentTextRef) {
            commentTextRef.contentEditable = 'false';
        }
        editableCommentContent = comment.content;
        isRedacting = false;
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
								                        {#if comment.removed && comment.removedBy}
						                                        <span class="moderated-info">(Moderated by {comment.removedBy})</span>
						                                {/if}
						                        </span>
										{/if}
								</div>
								<!-- INPUT BOX -->
								<p  class="comment-text"
								    bind:this={commentTextRef}
								    class:is-redacting={isRedacting}
								    oninput={isRedacting ? handleEditableContentInput : undefined}
								    role={isRedacting ? "textbox" : undefined}
								    aria-multiline={isRedacting ? "true" : undefined}
								>
										{#if comment.removed && comment.content === "Comment has been deleted by moderation."}
												<em>{comment.content}</em>
										{:else if isRedacting}
												{editableCommentContent} <!-- state for direct editing -->
										{:else}
												{@html comment.content.replace(/\n/g, '<br>')} <!-- normal content, newlines are <br> -->
										{/if}
								</p>
								
								{#if isRedacting}
										<div class="redaction-controls">
												<button class="action-button" onclick={insertBlockCharsAtSelection} title="Replace selected text with ■">Redact Selected</button>
												<button class="action-button save-redaction-button" onclick={saveRedaction}>Save Redaction</button>
												<button class="action-button cancel-redaction-button" onclick={cancelRedaction}>Cancel</button>
										</div>
								{/if}
								
								<div class="comment-actions">
										{#if !isRedacting}
												<button class="action-button reply-button" onclick={handleReplyClick} disabled={comment.removed}>Reply</button>
												{#if canModerate && !comment.removed} <!-- show delete only if not fully removed -->
														<button class="action-button delete-button" onclick={toggleModerationOptions}>
																{showModerationOptions ? 'Cancel Moderation' : 'Moderate'}
														</button>
												{/if}
										{/if}
								</div>
								
								{#if showModerationOptions && !isRedacting}
										<div class="moderation-options">
												<button class="action-button moderate-action-button" onclick={handleFullDelete}>Delete Entire Comment</button>
												<button class="action-button moderate-action-button" onclick={startRedaction}>Redact Part of Comment</button>
										</div>
								{/if}
						</div>
				</div>
				
				{#if showReplyInput && !isRedacting}
						<div class="reply-input-area">
                <textarea
		                bind:this={replyInputRef}
		                bind:value={replyContent}
		                placeholder="Write your reply..."
		                rows="1"
		                class="reply-textarea"
		                oninput={autoResizeReplyTextarea}
                ></textarea>
								<div class="reply-input-actions">
										<button class="action-button post-reply-button" onclick={handlePostReplySubmit} disabled={!replyContent.trim()}>Post Reply</button>
										<button class="action-button cancel-reply-button" onclick={() => { showReplyInput = false; replyContent = ''; }}>Cancel</button>
								</div>
						</div>
				{/if}
				
				{#if replies.length > 0}
						<div class="comment-replies">
								{#each replies as reply (reply.id)}
										<Self
												comment={reply}
												{allComments}
												{onReply}
												{onPostReply}
												{onModerateComment}
												{currentArticleId}
												level={level + 1}
										/>
								{/each}
						</div>
				{/if}
		</div>
</div>
{#if level === 0 && !comment.removed}
		<hr class="comment-separator" />
{:else if level === 0 && comment.removed && comment.content === "Comment has been deleted by moderation."}
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

    .comment-text.is-redacting {
        border: 1px dashed #007bff;
        padding: 5px;
        min-height: 50px; /* Ensure it's clickable */
        background-color: #f8f9fa;
        white-space: pre-wrap; /* Keep for editing */
    }
    .comment-text:focus-visible {
        outline: 2px solid #007bff;
    }

    .redaction-controls {
        display: flex;
        gap: 10px;
        margin-top: 8px;
        padding-left: 52px; /* Align with reply input area */
    }
    .save-redaction-button {
        color: #28a745; /* Green for save */
    }

    .moderation-options {
        margin-top: 8px;
        padding-left: 52px; /* Align with reply input area */
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 5px;
        border-left: 2px solid #ffc107; /* Yellow to indicate moderation mode */
        padding-right: 8px;
        background-color: #fffadf;
        border-radius: 4px;
    }
    .moderate-action-button {
        font-size: 0.85em;
    }
    .moderated-info {
        font-size: 0.8em;
        color: #6c757d;
        font-style: italic;
        margin-left: 10px;
    }
    
</style>