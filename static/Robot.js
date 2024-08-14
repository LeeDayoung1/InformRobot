const images = ["image/emo1.jpg", "image/emo2.jpg", "image/emo3.jpg", "image/emo4.jpg"];
const slideshow = document.getElementById("slideshow");

function changeImage() {
    const randomIndex = Math.floor(Math.random() * images.length);
    slideshow.src = images[randomIndex];
}

setInterval(changeImage, 1000);
window.onload = changeImage; // Change image immediately on load
