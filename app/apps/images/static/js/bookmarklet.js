const siteUrl = window.bookmarkletSiteUrl;
const styleUrl = siteUrl + 'static/css/bookmarklet.css';
const minWidth = 250;
const minHeight = 250;


// load CSS
const head = document.getElementsByTagName('head')[0];
const link = document.createElement('link');
link.rel = 'stylesheet';
link.type = 'text/css';
link.href = styleUrl + '?r=' + Math.floor(Math.random()*9999999999999999);
head.appendChild(link);


// load HTML
const body = document.getElementsByTagName('body')[0];
const boxHtml = `
    <div id="bookmarklet">
        <a href="#" id="close">&times;</a>
        <h1>Select an image to bookmark:</h1>
        <div class="images"></div>
    </div>`;
body.insertAdjacentHTML('beforeend', boxHtml);


function bookmarkletLaunch() {
    const bookmarklet = document.getElementById('bookmarklet');
    const imagesFound = bookmarklet.querySelector('.images');

    imagesFound.innerHTML = '';
    bookmarklet.style.display = 'block';
    bookmarklet.querySelector('#close')
        .addEventListener('click', () => {
            bookmarklet.style.display = 'none';
        });

    // find images in DOM with minimum dimensions
    const images = document.querySelectorAll(
        'img[src$=".jpg"], img[src$=".jpeg"], img[src$=".png"], img[src$=".webp"]'
    );
    images.forEach(image => {
        if (image.naturalWidth >= minWidth && image.naturalHeight >= minHeight) {
            const imageFound = document.createElement('img');
            imageFound.src = image.src;
            imagesFound.append(imageFound);
        }
    });

    // image selection event
    imagesFound.querySelectorAll('img').forEach(image => {
        image.addEventListener('click', (event) => {
            const imageSelected = event.target;
            bookmarklet.style.display = 'none';
            const params = new URLSearchParams({
                url: imageSelected.src,
                title: document.title,
            });
            window.open(`${siteUrl}images/create/?${params}`, '_blank');
        });
    });
}

