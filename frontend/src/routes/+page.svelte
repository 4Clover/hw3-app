<script lang="ts" >
    import {onMount, onDestroy} from 'svelte'; // functions to activate on component mount and dismount from the DOM
    import {BROWSER} from 'esm-env'; // sveltekit environment variable, used to check if user is in the browser or not
    import '../app.css'; // global CSS file
    import CommentSection from '$lib/CommentSection.svelte';
    import type { Comment as CommentType } from '$lib/CommentSection.svelte';
    
    interface Article { // format of the data received from the backend
        id: number,
        headline: string,
        author: string,
        content: string,
        imageUrl: string | null,
        articleUrl: string
    }
	
    // --- Comment type reference ---
    // Comment {
    //     id: string;
    //     author: string;
    //     content: string;
    //     articleId: string;
    //     removed: boolean;
    //     removedBy: string;
    //     timestamp?: number; // optional
    // }
    
	
    // --- Constants ---
    const THROTTLE_DELAY = 1000; // in milliseconds i.e. 1 second
    const RESIZE_DEBOUNCE_DELAY = 150; // milliseconds
    const API_BASE_QUERY = 'sacramento';
    const API_BEGIN_DATE = '20230401';
    const API_FILTER_LOCATION = 'timesTags.location.includes=california';
    const REMOVED_TEXT_FILL = '&block';

    // --- Component State ---
	
    // UI State
    let currentDate: string = 'Loading Date...';
    let currentYear: string = new Date().getFullYear().toString();
    let isSidebarOpen: boolean = false;

    // Sticky Navigation State
    let mainNavElement: HTMLElement | null = null;
    let navHeight: number = 0;
    let stickyPoint: number = 0; // updated on window resize
    let isSticky: boolean = false;
    let resizeTimeoutId: ReturnType<typeof setTimeout> | null = null; // for debouncing on resize

    // Articles State
    let articles: Article[] = [];
    let articlesError: string | null = null;
    let useMockApi: boolean = false; // true if testing (PRIOR: fake_articles)
    
    // Comments State
    let allComments: CommentType[] = [];
    let commentsError: string | null = null;
    let isLoadingComments: boolean = true;
    let postCommentErrors: { [articleId: string]: string | null } = {};
    
    // User state
    let userFound: boolean = false;

    // Infinite Scroll State
    let isLoadingInitArticles: boolean = true;
    let isLoadingMoreArticles: boolean = false;
    let currentPage: number = 0;
    let hasMoreArticles: boolean = true;
    let infinitePointElement: HTMLDivElement | null = null;
    let observer: IntersectionObserver | null = null;
    let observerInitialized: boolean = false;
    let isThrottled: boolean = false;
    let throttleTimeoutId: ReturnType<typeof setTimeout> | null = null;

    // --- UI Update Functions ---
    function updateDate() {
        const today = new Date();
        const options: Intl.DateTimeFormatOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        currentDate = today.toLocaleDateString('en-US', options);
    }
    function openSidebar() {
        isSidebarOpen = true;
    }
    function closeSidebar() {
        isSidebarOpen = false;
    }

    // --- Sticky Navigation Handler ---
    function handleStickyNavScroll() {
        if (!mainNavElement || !BROWSER) return;
        // validate stickyPoint after recalc
        if (stickyPoint > 0 && window.scrollY > stickyPoint) {
            if (!isSticky) {
                console.log(`Nav is now sticky. ScrollY: ${window.scrollY}, StickyPoint: ${stickyPoint}`);
                isSticky = true;
            }
        } else {
            if (isSticky) {
                console.log(`Nav is now static. ScrollY: ${window.scrollY}, StickyPoint: ${stickyPoint}`);
                isSticky = false;
            }
        }
    }
    
    // --- Recalculate Sticky Point Function ---
    function updateStickyPoint() {
        if (!mainNavElement || !BROWSER) return;
        // recalc based on CURRENT position
        stickyPoint = mainNavElement.offsetTop;
        navHeight = mainNavElement.offsetHeight;
        console.log(`Recalculated - Sticky Point: ${stickyPoint}px, Nav Height: ${navHeight}px`);
        handleStickyNavScroll(); // immediately handle for cases where resizing WITHOUT scrolling crosses the threshold
    }

    // --- Debounced Resize Handler ---
    function handleResize() {
        if (!BROWSER) return;
        if (resizeTimeoutId) clearTimeout(resizeTimeoutId);
        resizeTimeoutId = setTimeout(updateStickyPoint, RESIZE_DEBOUNCE_DELAY);
    }

    // --- API Helper Functions ---
    function buildApiUrl(page: number, mock: boolean): string {
        const baseUrl = mock ? '/api/test_articles' : '/api/search'; // if mock true, use testing articles
        if (mock) {
            return baseUrl;
        }
        return `${baseUrl}?query=${encodeURIComponent(API_BASE_QUERY)}&begin_date=${API_BEGIN_DATE}&filter=${encodeURIComponent(API_FILTER_LOCATION)}&page=${page}`;
    }
	
    // --- Response Processing w/ error checking on formatting or return type ---
    function processApiResponse(newArticlesData: any, pageToFetch: number) {
        if (!Array.isArray(newArticlesData)) { // incorrect return type
            if (typeof newArticlesData === 'object' && newArticlesData !== null && 'error' in newArticlesData) {
                throw new Error(`API Error: ${(newArticlesData as {error: string}).error}`);
            }
            console.error("Unexpected API response format:", newArticlesData);
            throw new Error("Unexpected data format received from API.");
        }

        const newArticles: Article[] = newArticlesData;
        console.log(`Fetched ${newArticles.length} articles for page ${pageToFetch}.`);

        if (newArticles.length === 0 && pageToFetch > 0) { // no articles to load
            hasMoreArticles = false;
            console.log("No more articles found.");
        } else if (newArticles.length > 0) { // append new articles
            const currentIds = new Set(articles.map(a => a.id));
            const uniqueNewArticles = newArticles.filter(a => a?.id && !currentIds.has(a.id));
            articles = [...articles, ...uniqueNewArticles];

            if (!useMockApi && newArticles.length < 10 && pageToFetch > 0) { // mockAPI checked here for loading purposes
                hasMoreArticles = false;
                // if less than 10 articles found, show in log
                console.log("Assuming no more articles based on count < 10 (actual count: " + newArticles.length + ").");
            }
        } else if (pageToFetch === 0 && newArticles.length === 0) {
            console.log("No articles found on initial fetch.");
        }
    }

    async function fetchArticlesPage(pageToFetch: number) {
        // timeout check (needed due to NYT api fetch rate limit -- ~3 calls per second
        if (pageToFetch === 0) {
            isLoadingInitArticles = true;
        } else {
            if (isLoadingMoreArticles) {
                console.warn(`Fetch attempt for page ${pageToFetch} blocked by concurrent loading.`);
                return;
            }
            isLoadingMoreArticles = true;
        }
        articlesError = null;

        const apiUrl = buildApiUrl(pageToFetch, useMockApi);
		
        // try-catch for fetch
        try {
            console.log(`Fetching page: ${pageToFetch} from ${apiUrl}`);
            const response = await fetch(apiUrl);

            if (!response.ok) {
                let errorBody = `HTTP error! status: ${response.status}`;
                try {
                    const errorJson = await response.json();
                    if (errorJson?.error) errorBody += ` - ${errorJson.error}`;
                    else if (errorJson?.message) errorBody += ` - ${errorJson.message}`;
                } catch { /*ignore and always print */ }
                throw new Error(errorBody);
            }

            const newArticlesData = await response.json();
            processApiResponse(newArticlesData, pageToFetch);

        } catch (e: any) {
            console.error(`Failed to fetch articles for page ${pageToFetch}:`, e);
            articlesError = e.message || `Unknown error loading articles (page ${pageToFetch})`;
        } finally {
            isLoadingInitArticles = false;
            isLoadingMoreArticles = false;
        }
    }

    // --- Comment Fetch and Post functions ---
    async function fetchAllComments() {
        isLoadingComments = true;
        commentsError = null;
        try {
            const response = await fetch('/api/comments');
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                throw new Error(`HTTP error ${response.status}: ${errorData.error || response.statusText}`);
            }
            const fetchedComments: CommentType[] = await response.json();
            if (!Array.isArray(fetchedComments)) {
                throw new Error("Invalid comments data format from API.");
            }
            allComments = fetchedComments.map(c => ({...c, id: String(c.id), articleId: String(c.articleId)}));
        } catch (e: any) {
            console.error('Failed to fetch comments:', e);
            commentsError = e.message || 'Unknown error loading comments.';
            allComments = [];
        } finally {
            isLoadingComments = false;
        }
    }


    // The 'event' parameter will now be the detail object directly
    async function handleCommentPost(detail: { articleId: string; author: string; content: string }) {
        const { articleId, author, content } = detail; // destructure from detail object (unbox)
        postCommentErrors = { ...postCommentErrors, [articleId]: null };

        try {
            // fetch POST formatting
            const response = await fetch('/api/comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ articleId, author, content })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Failed to parse error response' }));
                throw new Error(errorData.error || `Failed to post comment (status: ${response.status})`);
            }

            await fetchAllComments(); // refetch after post to update UI
        } catch (e: any) {
            console.error(`Failed to post comment for article ${articleId}:`, e);
            postCommentErrors = { ...postCommentErrors, [articleId]: e.message || 'Unknown error posting comment.' };
        }
    }
    
    // TODO: MODERATION
    // --- Moderate Comment ---
    
    
    // --- Moderate Parts of a Comment ---
    
    
    
    // TESTER FUNCTION -- not in use other than initial check for DB connection
    async function testGetAndLogComments() {
        console.log('Testing MongoDB by fetching comments from /api/comments...');
        try {
            const response = await fetch('/api/comments');
            if (!response.ok) {
                console.error(`HTTP error! Status: ${response.status}`);
                const errorBody = await response.text();
                console.error('Error response body:', errorBody);
                return;
            }
            const testData = await response.json();
            console.log('Comments from /api/comments (testGetAndLogComments): \n', testData);
        } catch (error) {
            console.error('Failed to fetch /api/comments in testGetAndLogComments:', error);
        }
    }
    
    // --- Intersection Observer Callback ---
    function onIntersection(entries: IntersectionObserverEntry[]) {
        const entry = entries[0];
        // check if not already loading, activate throttle, release after timer
        if (entry.isIntersecting && hasMoreArticles && !isLoadingMoreArticles && !isLoadingInitArticles && !isThrottled) {
            console.log('Watcher visible AND not throttled, loading next page...');
            isThrottled = true;
            console.log(`Throttling activated. Cooldown: ${THROTTLE_DELAY}ms`);
            currentPage++;
            fetchArticlesPage(currentPage);

            if (throttleTimeoutId) clearTimeout(throttleTimeoutId);
            throttleTimeoutId = setTimeout(() => {
                isThrottled = false;
                console.log('Throttle released.');
            }, THROTTLE_DELAY);
        } else if (entry.isIntersecting) {
            console.log('Watcher visible but not loading (conditions not met):', { hasMoreArticles, isLoadingMoreArticles, isLoadingInitArticles, isThrottled });
        }
    }

    let userEmail: string = "";
    async function isLoggedIn()
    {
        const response = await fetch('/api/getUser');
        if (!response.ok) {
            console.error(`HTTP error! Status: ${response.status}`);
            const errorBody = await response.text();
            console.error('Error response body:', errorBody);
            return;
        }
        const userData = await response.json();
        if (userData.user_email)
        {
            userFound = true;
            userEmail = userData.user_email;
        }
        else
        {
            userFound = false; // for safety purposes
            userEmail = "null"; // for safety purposes
        }
    }

    // using this resource to help me with window location! 
    // https://www.w3schools.com/js/js_window_location.asp
    function handleLogin() {
        window.location.href = 'api/login';

    }
    function handleLogout() {
        window.location.href = 'api/logout';
    }

    // --- Lifecycle Hooks ---
    onMount(() => {
        if (!BROWSER) return;
        updateDate();
        fetchArticlesPage(currentPage); // init articles fetch
        fetchAllComments(); // init comments fetch
        testGetAndLogComments(); // testing MongoDB via actual data fetching
	    isLoggedIn();

        if (mainNavElement) {
            setTimeout(() => {
                updateStickyPoint(); // on mount calculation
                if (navHeight > 0) {
                    window.addEventListener('scroll', handleStickyNavScroll, { passive: true }); // passive so not updating every tick
                    window.addEventListener('resize', handleResize);
                    console.log(`Sticky nav initialized.`);
                } else {
                    console.warn('Sticky navigation disabled: Nav element height is 0 on mount.');
                }
            }, 100); // milliseconds delay for layout stability

        } else {
            console.warn('Main navigation element not found for sticky setup.');
        }
    });
	
    // --- Reactive Code for Observer ---
    // '$' is a reactive statement for any variables within the code block
    $: if (BROWSER && !isLoadingInitArticles && infinitePointElement && !observerInitialized && hasMoreArticles) {
        console.log("Conditions met, setting up Intersection Observer...");
        observer = new IntersectionObserver(onIntersection, {
            rootMargin: '300px' // preload for infinite scroll ease of viewing, hard to perfect given NYT API limit
        });
        observer.observe(infinitePointElement);
        observerInitialized = true;
        console.log("Intersection Observer is set up reactively.");
    } else if (BROWSER && observerInitialized && !hasMoreArticles && observer) {
        console.log("No more articles expected or observer conditions changed, disconnecting observer.");
        observer.disconnect();
        observer = null; // clear the observer
        observerInitialized = false; // reset init
    }

    onDestroy(() => {
        if (observer) {
            observer.disconnect();
            console.log("Intersection Observer disconnected.");
        }
        if (throttleTimeoutId) {
            clearTimeout(throttleTimeoutId);
            console.log("Throttle timeout cleared.");
        }
        if (resizeTimeoutId) {
            clearTimeout(resizeTimeoutId);
        }
        if (BROWSER) {
            window.removeEventListener('scroll', handleStickyNavScroll);
            window.removeEventListener('resize', handleResize);
            console.log("Scroll and resize listeners removed.");
        }
    });
</script>


<!-- Header -->
<header>
		<!-- Top bar -->
		<div class="top-bar">
				<div class="top-bar-left">
						<span>&#x1F50D</span> <!-- Magnifying glass -->
				</div>
				<div class="top-bar-center">
						<span><a href="# ">U.S.</a></span>
						<span><a href="# ">International</a></span>
						<span><a href="# ">Canada</a></span>
						<span><a href="# ">Español</a></span>
						<span><a href="# ">中文</a></span>
				</div>
				<div id="top-bar-right">
                    <!-- TODO: Make side panel for My Account to show userEmail and log out button -->
					{#if userFound} 
                    <span>
                        <a href="#" >My Account</a>
                        <button class='login-button' on:click={handleLogout}>Log Out</button>
                    </span>
                    {:else} <button class='login-button' on:click={handleLogin}>Log In</button>
                    {/if}
				</div>
		</div>
		<!-- Title bar -->
		<div class="title-bar">
				<div class="title-bar-left">
						<span id="current-date">{currentDate}</span>
				</div>
				<div class="title-bar-center">
						<h1>The New York Times</h1>
				</div>
				<div id="title-bar-right">
						<span class="market-widget">DOW +1000% ↑</span>
				</div>
		</div>
		<!-- Persistent nav bar -->
		<nav class="main-nav-bar" class:isSticky bind:this={mainNavElement}>
				<!-- Mobile menu button -->
				<button
						class="nav-toggle"
						aria-label="Open navigation menu"
						aria-expanded={isSidebarOpen}
						aria-controls="mobile-sidebar"
						on:click={openSidebar}
				>
						☰
				</button>
				<!-- Navigation links -->
				<ul>
						<li><a href="# ">U.S.</a></li>
						<li><a href="# ">World</a></li>
						<li><a href="# ">Business</a></li>
						<li><a href="# ">Arts</a></li>
						<li><a href="# ">Lifestyle</a></li>
						<li><a href="# ">Opinion</a></li>
						<li class="main-nav-bar-divider">|</li>
						<li><a href="# ">Audio</a></li>
						<li><a href="# ">Games</a></li>
						<li><a href="# ">Cooking</a></li>
						<li><a href="# " >Wirecutter</a></li>
						<li><a href="# ">The Athletic</a></li>
				</ul>
		</nav>
		
		<!-- MOBILE NAV MENU -->
		<aside class="mobile-sidebar" class:open={isSidebarOpen} id="mobile-sidebar" aria-hidden={!isSidebarOpen}>
				<button class="close-mobile-sidebar" aria-label="Close navigation menu" on:click={closeSidebar}>x</button>
				<ul>
						<li><a href="# " on:click={closeSidebar}>U.S.</a></li>
						<li><a href="# " on:click={closeSidebar}>World</a></li>
						<li><a href="# " on:click={closeSidebar}>Business</a></li>
						<li><a href="# " on:click={closeSidebar}>Arts</a></li>
						<li><a href="# " on:click={closeSidebar}>Lifestyle</a></li>
						<li><a href="# " on:click={closeSidebar}>Opinion</a></li>
						<li class="mobile-divider"></li>
						<li><a href="# " on:click={closeSidebar}>Audio</a></li>
						<li><a href="# " on:click={closeSidebar}>Games</a></li>
						<li><a href="# " on:click={closeSidebar}>Cooking</a></li>
						<li><a href="# " on:click={closeSidebar}>Wirecutter</a></li>
						<li><a href="# " on:click={closeSidebar}>The Athletic</a></li>
						<li class="mobile-divider"></li>
						<li><a href="# " on:click={closeSidebar}>Search</a></li>
						<li><a href="# " on:click={closeSidebar}>Log In</a></li>
				</ul>
		</aside>
		
		<!-- DIMMER -->
		<div class="overlay" class:active={isSidebarOpen} aria-label="Close navigation menu"></div>


</header>

<!-- Body -->
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
										<article>
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
												<p class="content">{article.content}</p>
												<!-- CommentSection component added here -->
												<CommentSection
														articleId={String(article.id)}
														commentsForArticle={allComments.filter(c => String(c.articleId) === String(article.id))}
														isLoading={isLoadingComments && allComments.filter(c => String(c.articleId) === String(article.id)).length === 0}
														postError={postCommentErrors[article.id] || null}
														onCommentPost={handleCommentPost}
												/>
										</article>
								{/each}
						</div>
						
						<!-- Loading / State Indicators -->
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

<!-- Footer -->
<footer>
		<div class="footer-nav-bar">
				<ul>
						<li><a href="# ">© <span id="current-year">{currentYear}</span> New York Lime, LLC </a></li>
						<li><a href="# ">Terms of Service</a></li>
						<li><a href="# ">Help</a></li>
				</ul>
		</div>
</footer>