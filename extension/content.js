// Grab all visible text on the page
let jobText = document.body.innerText;
let url = window.location.href;

// Store result globally so popup can fetch it
window.__SCRAPER_RESULT__ = `
URL: ${url}

---------------- PAGE TEXT ----------------
${jobText}
-------------------------------------------
`;
