<script lang="ts">
    export interface Comment { // format of the actual comment data type
        id: string;
        author: string;
        content: string;
        articleId: string;
        removed: boolean;
        removedBy: string;
        timestamp?: number;
    }
    // callback prop type
    type PostCommentDetail = {
        articleId: string;
        author: string;
        content: string;
    };
    type PostCommentCallback = (detail: PostCommentDetail) => void;
	
    // comment prop interface (the object passed to the main page for serving)
    interface CommentProps {
        articleId: string;
        commentsForArticle?: Comment[];
        isLoading?: boolean;
        postError?: string | null;
        onCommentPost?: PostCommentCallback; // callback prop
    }
    let {
        articleId,
        commentsForArticle = [],
        isLoading = false,
        postError = null,
        onCommentPost // destructuring the prop -- taking an object and unboxing it into its sub-parts
    }: CommentProps = $props();
    
    // declare as state for updating on the main page (makes the data visible)
    let newCommentAuthor: string = $state('Anonymous');
    let newCommentContent: string = $state('');
    
    // take comment data as a prop and callback to main page
    const formIdPrefix = $props.id();
    function handleSubmitComment() {
        if (!newCommentContent.trim()) {
            alert('Comment content cannot be empty.');
            return;
        }
        if (!newCommentAuthor.trim()) {
            newCommentAuthor = 'Anonymous';
        }
        // call the callback prop if present
        if (onCommentPost) {
            onCommentPost({
                articleId: articleId,
                author: newCommentAuthor,
                content: newCommentContent
            });
        } else {
            console.warn(`CommentSection: onPostcomment callback not provided for articleId ${articleId}`);
        }
        newCommentContent = '';
    }
    
</script>

<div class="comment-section-component">
		<h4>Comments</h4>
		
		{#if isLoading && commentsForArticle.length === 0}
				<p>Loading comments...</p>
		{/if}
		
		<div class="comments-list-container">
				{#if commentsForArticle.length > 0}
						{#each commentsForArticle as comment (comment.id)}
								<div class="comment-box">
										<p class="comment-author">
												{comment.author}
												{#if comment.timestamp}
							<span class="comment-timestamp">
								- {new Date(comment.timestamp * 1000).toLocaleString()} <!-- Needs updating to a more standard time -->
							</span>
												{/if}
										</p>
										<p class="comment-content">
												{#if comment.removed}
														<s class="removed-comment-content">{comment.content}</s>
														<br />
														<!-- TODO: Change code for moderation removal per HW -->
														<em class="removed-comment-by">(Comment removed by {comment.removedBy || 'moderator'})</em>
												{:else}
														{comment.content}
												{/if}
										</p>
								</div>
						{/each}
				{:else if !isLoading}
						<p>Share your opinion... if you dare.</p>
				{/if}
		</div>
		
		
		<div class="post-comment-form">
				<h5>Leave a Comment</h5>
				{#if postError}
						<p class="post-error">{postError}</p>
				{/if}
				<div class="form-group">
						<label for="{formIdPrefix}-author" class="form-label">Name:</label>
						<!--
						        TEMP NAME INPUT, WILL CHANGE AFTER AUTH
								TODO: Implement Auth/Login
						-->
						<input
								type="text"
								id="{formIdPrefix}-author"
								bind:value={newCommentAuthor}
								placeholder="Your Name"
								class="form-input"
						/>
				</div>
				<!-- User input box -->
				<div class="form-group">
						<label for="{formIdPrefix}-content" class="form-label">Comment:</label>
						<textarea
								id="{formIdPrefix}-content"
								bind:value={newCommentContent}
								placeholder="Write your comment here..."
								rows="4"
								class="form-textarea"
						></textarea>
				</div>
				<!-- Post comment button -->
				<button class="post-comment-button"
				        onclick={handleSubmitComment}
				        disabled={!newCommentContent.trim() || isLoading}
				>
				Post Comment
				</button>
		</div>
</div>

<!-- LOCAL STYLING TO AVOID HUGE MAIN CSS FILE -->
<style>
	.comments-list-container {
		max-height: 300px;
		overflow-y: auto;
		border: 1px solid #e0e0e0;
		padding: 10px;
		margin-bottom: 15px;
		background-color: #fdfdfd;
	}
	.comment-box {
        font-family: "Arial Black", Gadget, sans-serif;
		border-bottom: 1px solid #eee;
		padding: 8px 0;
		margin-bottom: 8px;
	}
	.comment-author {
		font-weight: bold;
		margin-bottom: 4px;
	}
	.comment-timestamp {
		font-size: 0.8em;
		color: #777;
		font-weight: normal;
	}
	.comment-content {
		white-space: pre-wrap;
		word-wrap: break-word;
	}
	.removed-comment-content {
		color: #888;
	}
	.removed-comment-by {
		color: #888;
		font-size: 0.9em;
	}
	.post-error {
		color: red;
		font-size: 0.9em;
	}
	.form-group {
		margin-bottom: 10px;
	}
	.form-label {
		display: block;
		margin-bottom: 4px;
		font-size: 0.9em;
	}
	.form-input {
		width: 100%;
		padding: 8px;
		box-sizing: border-box;
		border: 1px solid #ccc;
		border-radius: 3px;
	}
	.form-textarea {
		width: 100%;
		padding: 8px;
		box-sizing: border-box;
		border: 1px solid #ccc;
		border-radius: 3px;
		resize: vertical;
	}
	.post-comment-button {
		padding: 10px 15px;
		background-color: #007bff;
		color: white;
		border: none;
		border-radius: 4px;
		cursor: pointer;
	}
</style>