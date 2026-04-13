(function() {
    if (!window.bookmarklet) {
        window.bookmarklet = 'loading';
        window.bookmarkletSiteUrl = '{{ site_url }}/';
        const bookmarklet_js = document.createElement('script');
        bookmarklet_js.src = `{{ site_url }}/static/js/bookmarklet.js?r=${Math.floor(
            Math.random() * 9999999999999999
        )}`;
        bookmarklet_js.addEventListener('load', () => {
            window.bookmarklet = true;
            bookmarkletLaunch();
        });
        document.body.appendChild(bookmarklet_js);
    }
    else if (window.bookmarklet === true) {
        bookmarkletLaunch();
    }
})();

