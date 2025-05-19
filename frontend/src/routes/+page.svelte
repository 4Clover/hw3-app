<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { BROWSER } from 'esm-env';
    import '../app.css';
    import CommentSection from '$lib/CommentSection.svelte';
    import type { PostNewCommentDetail, PostNewReplyDetail } from '$lib/CommentSection.svelte';
    import type { Comment as CommentType } from '$lib/CommentItem.svelte';
    import { userStore, fetchUserStatus } from '$lib/stores/userStore.svelte';
    
    interface Article { // type returned from backend api call
        id: string;
        headline: string;
        author: string;
        content: string;
        imageUrl: string | null;
        articleUrl: string;
    }
	
    // --- Constants ---
    const THROTTLE_DELAY = 12000; // 12,000 milliseconds = 12 seconds = 5 per min = NYT rate limit
    const RESIZE_DEBOUNCE_DELAY = 150;
    const API_BASE_QUERY = 'sacramento';
    const API_BEGIN_DATE = '20230401';
    const API_FILTER_LOCATION = 'timesTags.location.includes=california';

    // --- UI States ---
    let currentDate = $state('Loading Date...');
    let currentYear = $state(new Date().getFullYear().toString());
    let isSidebarOpen = $state(false);

    // --- Main Nav States ---
    let mainNavElement: HTMLElement | null = null;
    let navHeight = $state(0);
    let stickyPoint: number = 0;
    let isSticky = $state(false);
    let resizeTimeoutId: ReturnType<typeof setTimeout> | null = null;

    // --- Article States ---
    let articles = $state<Article[]>([]);
    let articlesError = $state<string | null>(null);
    let useMockApi = $state(false);

    // --- Comment States ---
    let allComments = $state<CommentType[]>([]);
    let commentsError = $state<string | null>(null);
    let isLoadingComments = $state(true);
    let postCommentErrors = $state<{ [articleId: string]: string | null }>({});
    let isCommentPanelOpen = $state(false);
    let currentPanelArticleId = $state<string | null>(null);
    let currentPanelArticleHeadline = $state<string | null>(null);

    // --- Article Serving and Scroll States ---
    let isLoadingInitArticles = $state(true);
    let isLoadingMoreArticles = $state(false);
    let currentPage = $state(0);
    let hasMoreArticles = $state(true);
    let infinitePointElement: HTMLDivElement | null = $state(null);
    let observer: IntersectionObserver | null = null; // managed by $effect
    let isThrottled = $state(false);
    let throttleTimeoutId: ReturnType<typeof setTimeout> | null = null;

    // --- Update Date Function ---
    function updateDate() {
        const today = new Date();
        const options: Intl.DateTimeFormatOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        currentDate = today.toLocaleDateString('en-US', options);
    }

    // --- Mobile Nav Sidebar Functions ---
    function openMobileNavSidebar() { isSidebarOpen = true; }
    function closeMobileNavSidebar() { isSidebarOpen = false; }

    // --- Comment Panel Functions ---
    function openCommentsPanel(articleId: string, headline: string) {
        currentPanelArticleId = articleId;
        currentPanelArticleHeadline = headline;
        isCommentPanelOpen = true;
        if (BROWSER) document.body.classList.add('panel-open-no-scroll');
    }

    function closeCommentsPanel() {
        isCommentPanelOpen = false;
        if (BROWSER) document.body.classList.remove('panel-open-no-scroll');
    }

    function handlePanelOverlayClick(event: MouseEvent) {
        if (event.target === event.currentTarget) {
            closeCommentsPanel();
        }
    }

    // --- Sticky Nav Functions ---
    function handleStickyNavScroll() {
        if (!mainNavElement || !BROWSER) return;
        if (stickyPoint > 0 && window.scrollY > stickyPoint) {
            if (!isSticky) isSticky = true;
        } else {
            if (isSticky) isSticky = false;
        }
    }

    function updateStickyPoint() {
        if (!mainNavElement || !BROWSER) return;
        stickyPoint = mainNavElement.offsetTop;
        navHeight = mainNavElement.offsetHeight;
        handleStickyNavScroll();
    }

    function handleResize() {
        if (!BROWSER) return;
        if (resizeTimeoutId) clearTimeout(resizeTimeoutId);
        resizeTimeoutId = setTimeout(updateStickyPoint, RESIZE_DEBOUNCE_DELAY);
    }

    // --- Article API Functions ---
    function buildApiUrl(page: number, mock: boolean): string {
        const baseUrl = mock ? '/api/test_articles' : '/api/search';
        if (mock) {
            return baseUrl;
        }
        return `${baseUrl}?query=${encodeURIComponent(API_BASE_QUERY)}&begin_date=${API_BEGIN_DATE}&filter=${encodeURIComponent(API_FILTER_LOCATION)}&page=${page}`;
    }

    function processApiResponse(newArticlesData: any, pageToFetch: number) {
        if (!Array.isArray(newArticlesData)) {
            if (typeof newArticlesData === 'object' && newArticlesData !== null && 'error' in newArticlesData) {
                Error(`API Error: ${(newArticlesData as {error: string}).error}`);
                // changed to standalone 'Error' as per Svelte 5 docs this throws the error ( instead of throw new Error(...) )
            }
            Error("Unexpected data format received from API for articles.");
        }

        const newFetchedArticles: Article[] = newArticlesData.map((a: Omit<Article, 'id'> & { id: unknown }) => ({
            ...a, // '...' spreading out /"the rest of" parameter:
	              // expands an iterable i.e., its shorthand for inputting all values of the variable that follows
            id: String(a.id)
        }));

        if (newFetchedArticles.length === 0 && pageToFetch > 0) {
            hasMoreArticles = false;
        } else if (newFetchedArticles.length > 0) {
            const currentIds = new Set(articles.map(a => a.id));
            const uniqueNewArticles = newFetchedArticles.filter(a => a?.id && !currentIds.has(a.id));
            articles = [...articles, ...uniqueNewArticles];

            if (!useMockApi && newFetchedArticles.length < 10 && pageToFetch > 0) {
                hasMoreArticles = false;
            }
        }
    }

    async function fetchArticlesPage(pageToFetch: number) {
        if (pageToFetch === 0) {
            isLoadingInitArticles = true;
        } else {
            if (isLoadingMoreArticles) return;
            isLoadingMoreArticles = true;
        }
        articlesError = null;
        const apiUrl = buildApiUrl(pageToFetch, useMockApi);
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                let errorBody = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    if (errorJson?.error) errorBody += ` - ${errorJson.error}`;
                    else if (errorJson?.message) errorBody += ` - ${errorJson.message}`;
                } catch { /* ignore */ }
                Error(errorBody);
            }
            const newArticlesData = await response.json();
            processApiResponse(newArticlesData, pageToFetch);
        } catch (e: any) {
            articlesError = e.message || `Unknown error loading articles (page ${pageToFetch})`;
        } finally {
            isLoadingInitArticles = false;
            isLoadingMoreArticles = false;
        }
    }

    // --- Comment Fetch (Get/Post) Functions ---

    // CommentSectionProps {
    //     articleId: string;
    //     articleTitle: string;
    //     allCommentsForArticle?: CommentType[];
    //     isLoading?: boolean;
    //     postError?: string | null;
    //     onPostNewComment: (detail: PostNewCommentDetail) => void;
    //     onPostNewReply: (detail: PostNewReplyDetail) => void;
    // }

    // CommentItemProps {
    //     comment: Comment;
    //     allComments: Comment[];
    //     onReply: (commentId: string) => void;
    //     onPostReply: (detail: { content: string; parentId: string }) => void;
    //     currentArticleId: string;
    //     level?: number;
    // }

    // Comment {
    //     id: string;
    //     author: string;
    //     content: string;
    //     articleId: string;
    //     removed: boolean;
    //     removedBy: string;
    //     timestamp?: number;
    //     parentId?: string | null;
    // }
    
    async function fetchAllComments() {
        isLoadingComments = true;
        commentsError = null;
        try {
            const response = await fetch('/api/comments');
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                Error(`HTTP error ${response.status} fetching comments: ${errorData.error || response.statusText}`);
            }
            const fetchedComments: CommentType[] = await response.json();
            if (!Array.isArray(fetchedComments)) {
                Error("Invalid comments data format received from API.");
            }
            // map the comments to the expected form for serving
            allComments = fetchedComments.map(c => ({
                ...c,
                id: String(c.id),
                articleId: String(c.articleId),
                parentId: c.parentId ? String(c.parentId) : null
            }));
        } catch (e: any) {
            commentsError = e.message || 'Unknown error loading comments.';
            allComments = [];
        } finally {
            isLoadingComments = false;
        }
    }
	
    async function handlePostNewTopLevelComment(detail: PostNewCommentDetail) {
        const { articleId, content } = detail;
        postCommentErrors = { ...postCommentErrors, [articleId]: null };
        try {
            const response = await fetch('/api/comments', { // post new comment
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ articleId, content })
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                Error(errorData.error || `Failed to post top-level comment (status: ${response.status})`);
            }
            await fetchAllComments();
        } catch (e: any) {
            postCommentErrors = { ...postCommentErrors, [articleId]: e.message || 'Unknown error posting top-level comment.' };
        }
    }
	
    // copy of previous function but with parent id
    async function handlePostNewReplyComment(detail: PostNewReplyDetail) {
        const { articleId, content, parentId } = detail;
        postCommentErrors = { ...postCommentErrors, [articleId]: null };
        try {
            const response = await fetch('/api/comments', { // post new comment
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ articleId, content, parentId }) // WITH PARENT ID!!!
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                Error(errorData.error || `Failed to post reply (status: ${response.status})`);
            }
            await fetchAllComments();
        } catch (e: any) {
            postCommentErrors = { ...postCommentErrors, [articleId]: e.message || 'Unknown error posting reply.' };
        }
    }

    // --- Infinite Scroll Observer Function ---
    function onIntersection(entries: IntersectionObserverEntry[]) {
        const entry = entries[0];
        let canScroll : boolean = !isLoadingMoreArticles && !isLoadingInitArticles && !isThrottled;
        if (entry.isIntersecting && hasMoreArticles && canScroll) {
            isThrottled = true;
            currentPage++; // iterate page for viewing on activate
            fetchArticlesPage(currentPage); // fetch new pages
	        
	        // if throttle present, clear, then set new throttle
            if (throttleTimeoutId) clearTimeout(throttleTimeoutId);
            throttleTimeoutId = setTimeout(() => {
                isThrottled = false;
            }, THROTTLE_DELAY);
        }
    }

    // --- DOM Functions ---
    onMount(() => {
        if (!BROWSER) return;
        updateDate();
        fetchArticlesPage(currentPage);
        fetchAllComments();
        fetchUserStatus();

        if (mainNavElement) {
            setTimeout(() => {
                updateStickyPoint();
                if (navHeight > 0) {
                    window.addEventListener('scroll', handleStickyNavScroll, { passive: true });
                    window.addEventListener('resize', handleResize);
                }
            }, 100);
        }
    });

    $effect(() => {
        if (!BROWSER) return () => {}; // cleanup function for SSR safety

        const currentInfinitePointEl = infinitePointElement;

        // Condition for Observer to exist and be Active:
        // - initial articles are loaded
	    // - there's an element to observe
	    // - more articles are available
	    // - observer isn't already set up
        if (!isLoadingInitArticles && currentInfinitePointEl && hasMoreArticles && !observer) {
            observer = new IntersectionObserver(onIntersection, {
                rootMargin: '300px'
            });
            observer.observe(currentInfinitePointEl);
        }
        
        // Condition for Observer to be Destroyed:
        // - if an observer exists
        // - conditions for its activity are no longer met
        else if (observer && (isLoadingInitArticles || !currentInfinitePointEl || !hasMoreArticles)) {
            observer.disconnect();
            observer = null;
        }

        return () => {
            if (observer) {
                observer.disconnect();
                observer = null;
            }
        };
    });

    onDestroy(() => { // called before unmount
        if (throttleTimeoutId) {
            clearTimeout(throttleTimeoutId);
        }
        if (resizeTimeoutId) {
            clearTimeout(resizeTimeoutId);
        }
        if (BROWSER) {
            window.removeEventListener('scroll', handleStickyNavScroll);
            window.removeEventListener('resize', handleResize);
            document.body.classList.remove('panel-open-no-scroll');
        }
    });

    // --- Current Panel Update Function ---
    const commentsForCurrentPanel = $derived(
        // derived means this variable depends on other states, and thus will update when they update
        currentPanelArticleId ? allComments.filter(
            c => String(c.articleId) === String(currentPanelArticleId)) : []
    );

</script>

<header>
		<div class="top-bar">
				<div class="top-bar-left"><span>&#128269</span></div>
				<div class="top-bar-center">
						<span><a href="# ">U.S.</a></span><span><a href="# ">International</a></span>
						<span><a href="# ">Canada</a></span><span><a href="# ">Español</a></span><span><a href="# ">中文</a></span>
				</div>
				<div id="top-bar-right">
						{#if $userStore?.loggedIn}
						<span>Hello, {$userStore.username || $userStore.email}!</span>
						<a href="/api/logout" class="login-button" style="margin-left: 10px;">Log Out</a>
						{:else}
						<a href="/api/login" class="login-button">Log In</a>
						{/if}
				</div>
		</div>
		<div class="title-bar">
				<div class="title-bar-left"><span id="current-date">{currentDate}</span></div>
				<div class="title-bar-center"><h1>The New York Times</h1></div>
				<div id="title-bar-right"><span class="market-widget">DOW +1000% ↑</span></div>
		</div>
		<nav class="main-nav-bar" class:isSticky bind:this={mainNavElement}>
				<button class="nav-toggle" onclick={openMobileNavSidebar} aria-label="Open navigation menu" aria-expanded={isSidebarOpen} aria-controls="mobile-sidebar">☰</button>
				<ul>
						<li><a href="# ">U.S.</a></li><li><a href="# ">World</a></li><li><a href="# ">Business</a></li>
						<li><a href="# ">Arts</a></li><li><a href="# ">Lifestyle</a></li><li><a href="# ">Opinion</a></li>
						<li class="main-nav-bar-divider">|</li>
						<li><a href="# ">Audio</a></li><li><a href="# ">Games</a></li><li><a href="# ">Cooking</a></li>
						<li><a href="# " >Wirecutter</a></li><li><a href="# ">The Athletic</a></li>
				</ul>
		</nav>
		<aside class="mobile-sidebar" class:open={isSidebarOpen} id="mobile-sidebar" aria-hidden={!isSidebarOpen}>
				<button class="close-mobile-sidebar" onclick={closeMobileNavSidebar} aria-label="Close navigation menu">x</button>
				<ul>
						<li><a href="# " onclick={closeMobileNavSidebar}>U.S.</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>World</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Business</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Arts</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Lifestyle</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Opinion</a></li>
						<li class="mobile-divider"></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Audio</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Games</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Cooking</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Wirecutter</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>The Athletic</a></li>
						<li class="mobile-divider"></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Search</a></li>
						<li><a href="# " onclick={closeMobileNavSidebar}>Log In</a></li>
				</ul>
		</aside>
		<div class="overlay" class:active={isSidebarOpen} onclick={closeMobileNavSidebar} aria-label="Close navigation menu (overlay)" role="graphics-object"></div>
</header>

<div class="main-content-area" style="{isSticky ? `padding-top: ${navHeight}px;` : ''}">
		<main id="main-content">
				{#if isLoadingInitArticles}
						<p>Loading Articles...</p>
				{:else if articlesError && articles.length === 0}
						<p style="color: red;">Error Loading Articles: {articlesError}</p>
				{:else if articles.length === 0 && !isLoadingInitArticles}
						<p>No articles were found.</p>
				{:else}
						<div class="content-grid">
								{#each articles as article (article.id)}
										<article class="article-card">
												<a href={article.articleUrl} target="_blank" rel="noopener noreferrer">
														<h2 class="headline">{article.headline}</h2>
												</a>
												{#if article.imageUrl}
														<img
																src={article.imageUrl.startsWith('http') ? article.imageUrl : `https://www.nytimes.com/${article.imageUrl}`}
																alt={article.headline}
																class="article-image"
														/>
												{/if}
												<p class="author">{article.author}</p>
												<div class="article-content-area">
														<p class="content">{article.content}</p>
												</div>
												<div class="article-actions">
														<button
																class="open-comments-panel-button"
																onclick={() => openCommentsPanel(String(article.id), article.headline)}
														>
																Open
														</button>
												</div>
										</article>
								{/each}
						</div>
						
						{#if isLoadingMoreArticles} <p>Loading more articles...</p> {/if}
						{#if !hasMoreArticles && articles.length > 0} <p>You've reached the end.</p> {/if}
						{#if articlesError && articles.length > 0} <p>Error loading more: {articlesError}</p> {/if}
						{#if hasMoreArticles} <div bind:this={infinitePointElement} style="height: 10px;"></div> {/if}
				{/if}
				{#if commentsError && allComments.length === 0}
						<p style="text-align: center; padding: 20px; color: red;">Could not load comments: {commentsError}</p>
				{/if}
		</main>
</div>

<footer>
		<div class="footer-nav-bar">
				<ul>
						<li><a href="# ">© <span id="current-year">{currentYear}</span> New York Lime, LLC </a></li>
						<li><a href="# ">Terms of Service</a></li>
						<li><a href="# ">Help</a></li>
				</ul>
		</div>
</footer>

{#if isCommentPanelOpen}
		<div class="comments-side-panel-overlay" onclick={handlePanelOverlayClick} role="dialog" aria-modal="true" aria-labelledby="comment-panel-title-label">
				<div class="comments-side-panel" class:open={isCommentPanelOpen}>
						<button class="comments-panel-close-button" onclick={closeCommentsPanel} aria-label="Close comments panel">×</button>
						{#if currentPanelArticleId && currentPanelArticleHeadline}
								<CommentSection
										articleId={currentPanelArticleId}
										articleTitle={currentPanelArticleHeadline}
										allCommentsForArticle={commentsForCurrentPanel}
										isLoading={isLoadingComments && commentsForCurrentPanel.length === 0}
										postError={postCommentErrors[currentPanelArticleId] || null}
										onPostNewComment={handlePostNewTopLevelComment}
										onPostNewReply={handlePostNewReplyComment}
								/>
						{:else}
								<p style="padding:20px; text-align:center;">Loading panel content...</p>
						{/if}
				</div>
		</div>
{/if}

<style>
    :global(body.panel-open-no-scroll) {
        overflow: hidden;
    }

    .comments-side-panel-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: var(--z-overlay, 1050);
        display: flex;
        justify-content: flex-end;
    }

    .comments-side-panel {
        background-color: var(--color-white, #ffffff);
        height: 100%;
        width: 33.33%;
        max-width: 450px;
        min-width: 300px;
        box-shadow: -5px 0 15px rgba(0, 0, 0, 0.15);
        transform: translateX(100%);
        transition: transform 0.3s ease-out;
        display: flex;
        flex-direction: column;
        position: fixed;
        top: 0;
        right: 0;
        z-index: calc(var(--z-overlay, 1040) + 1);
    }
    .comments-side-panel.open {
        transform: translateX(0%);
    }

    .comments-panel-close-button {
        position: absolute;
        top: 10px;
        right: 15px;
        background: transparent;
        border: none;
        font-size: 2rem;
        font-weight: bold;
        color: var(--color-text-muted, #555555);
        cursor: pointer;
        line-height: 1;
        padding: 0;
        z-index: 10;
    }
    .comments-panel-close-button:hover {
        color: var(--color-text-default, #333333);
    }
    #top-bar-right span {
        margin-right: 10px;
        color: var(--color-text-muted);
    }
    
    
    @media (max-width: 767px) {
        .comments-side-panel {
            width: 80%;
            min-width: 280px;
            max-width: none;
        }
    }
</style>