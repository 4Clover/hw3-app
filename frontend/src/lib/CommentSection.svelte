<script lang="ts">
    import CommentItem from './CommentItem.svelte';
    import type { Comment as CommentType } from './CommentItem.svelte';

    export interface PostNewCommentDetail {
        articleId: string;
        content: string;
    }

    export interface PostNewReplyDetail {
        articleId: string;
        content: string;
        parentId: string;
    }

    export interface CommentSectionProps {
        articleId: string;
        articleTitle: string;
        allCommentsForArticle?: CommentType[];
        isLoading?: boolean;
        postError?: string | null;
        onPostNewComment: (detail: PostNewCommentDetail) => void;
        onPostNewReply: (detail: PostNewReplyDetail) => void;
        onModerateComment: (detail: { commentId: string; action: 'delete_full' | 'redact_partial'; newContent?: string }) => Promise<boolean>;
    }

    let {
        articleId,
        articleTitle,
        allCommentsForArticle = [],
        isLoading = false,
        postError = null,
        onPostNewComment,
        onPostNewReply,
        onModerateComment
    }: CommentSectionProps = $props();

    let newCommentContent = $state('');
    let mainCommentTextareaRef: HTMLTextAreaElement | null = $state(null);

    const topLevelComments = $derived(
        allCommentsForArticle
            .filter(c => !c.parentId)
            .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
    );

    const totalCommentsCount = $derived(allCommentsForArticle.length);

    function handleSubmitNewComment() {
        if (!newCommentContent.trim()) {
            alert('Comment content cannot be empty.');
            return;
        }
        onPostNewComment({
            articleId: articleId,
            content: newCommentContent
        });
        newCommentContent = '';
        if (mainCommentTextareaRef) {
            mainCommentTextareaRef.style.height = 'auto';
        }
    }

    function handlePostReplyFromItem(detail: { content: string; parentId: string }) {
        onPostNewReply({
            articleId: articleId,
            content: detail.content,
            parentId: detail.parentId
        });
    }

    function handleReplyInitiated(commentId: string) {
        // placeholder for max thread depth reached
    }

    function autoResizeMainTextarea(event: Event) {
        const textarea = event.target as HTMLTextAreaElement;
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    }
</script>

<div class="comment-section-panel-content">
		<!-- ... (panel-header, main-comment-input-area remain the same) ... -->
		<div class="panel-header">
				<h3 class="article-title-header">{articleTitle}</h3>
				<h4 class="comments-count-header">
						Comments {totalCommentsCount}
				</h4>
		</div>
		
		<div class="main-comment-input-area">
		<textarea
				bind:this={mainCommentTextareaRef}
				bind:value={newCommentContent}
				placeholder="Share your thoughts..."
				rows="2"
				class="main-comment-textarea"
				oninput={autoResizeMainTextarea}
		></textarea>
				<button
						class="post-main-comment-button"
						onclick={handleSubmitNewComment}
						disabled={!newCommentContent.trim() || isLoading}
				>
						Post Comment
				</button>
				{#if postError}
						<p class="post-error-message">{postError}</p>
				{/if}
		</div>
		
		<div class="comments-list-container" tabindex="0">
				{#if isLoading && allCommentsForArticle.length === 0}
						<p class="loading-text">Loading...</p>
				{:else if topLevelComments.length > 0}
						{#each topLevelComments as comment (comment.id)}
								<CommentItem
										{comment}
										allComments={allCommentsForArticle}
										onReply={handleReplyInitiated}
										onPostReply={handlePostReplyFromItem}
										{onModerateComment}
										currentArticleId = {articleId}
								level={0}
								/>
						{/each}
				{:else if !isLoading}
						<p class="no-comments-text">Share your thoughts... if you dare!</p>
				{/if}
		</div>
</div>

<style>
    .comment-section-panel-content {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
    }

    .panel-header {
        padding: 15px 20px;
        border-bottom: 1px solid #e9ecef;
        flex-shrink: 0;
        overflow: hidden; /* contains title if too large */
    }
    .article-title-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #333;
        margin: 0 0 5px 0;
        line-height: 1.3;
        white-space: nowrap; /* one line no wrap */
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .comments-count-header {
        font-size: 1rem;
        font-weight: bold;
        color: #555;
        margin: 0;
    }

    .main-comment-input-area {
        padding: 15px 20px;
        border-bottom: 1px solid #e9ecef;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .main-comment-textarea {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 0.95em;
        line-height: 1.5;
        resize: none;
        overflow-y: hidden;
        min-height: 50px;
        box-sizing: border-box;
        transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    .main-comment-textarea:focus {
        border-color: #80bdff;
        outline: 0;
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }
    .post-main-comment-button {
        align-self: flex-end;
        padding: 8px 15px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
    }
    .post-main-comment-button:disabled {
        background-color: #cccccc;
        cursor: not-allowed;
    }
    .post-error-message {
        color: red;
        font-size: 0.85em;
        margin-top: 5px;
    }

    .comments-list-container {
        flex-grow: 1;
        overflow-y: auto;
        padding: 15px 20px 15px 5px;
        -ms-overflow-style: none;  /* IE and Edge */
        scrollbar-width: none;  /* Firefox */
    }
    .comments-list-container::-webkit-scrollbar { /* WebKit browsers */
        display: none;
    }
    .loading-text, .no-comments-text {
        color: #6c757d;
        text-align: center;
        padding: 20px;
    }
</style>