import { describe, test, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/svelte';
// import Page from './+page.svelte';
// @ts-ignore
import Page from '+page.svelte'
// Following testing structure from: https://svelte.dev/docs/svelte/testing

interface Article { // format of the data received from the backend
	id: number,
	headline: string,
	author: string,
	content: string,
	imageUrl: string,
	articleUrl: string
}

let articles: Article [] = []; // array of articles to be used in the test
const isTest : boolean = true;

describe('/+page.svelte', () => {
	test('should render h1', () => {
		render(Page);
		expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
	});
});

// ----------------- Alyssa's Testing -----------------
test('fake_fetchArticles', () => {
	// articles = fetchArticles(isTest);
	expect(articles[0]).toEqual(
		{
			"id": "nyt1",
			"headline": "Breaking: Lime Shortage Sparks Citrus Panic",
			"imageUrl": "/images/1.png",
            "author": "Zesty Lemonsworth",
            "content": "Citizens storm supermarkets as lime shelves empty overnight..."
		});
});

// Date checking test
test('current_date_test', () => {
	const dayofweek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
	const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
	const currentDate = new Date();
	const YYYY = currentDate.getFullYear();
	const DD = currentDate.getDate();

	// Should be Day of week, Month Day, Year format
	// e.g. Wednesday, October 4, 2023
	const DotW = dayofweek[currentDate.getDay()];
	const MM = months[currentDate.getMonth()];
	const correctFullDate = `${DotW}, ${MM} ${DD}, ${YYYY}`;
	// expect(updateDate()).toEqual(correctFullDate);

});