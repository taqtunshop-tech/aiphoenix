// script.js
document.addEventListener("DOMContentLoaded", () => {
    // Add subtle random rotation to all sketchy tags to make them look hand-placed
    const tags = document.querySelectorAll('.sketchy-tag');
    tags.forEach(tag => {
        // Random angle between -2 and 2 degrees
        const randomAngle = (Math.random() * 4) - 2;
        tag.style.transform = `rotate(${randomAngle}deg)`;
    });

    // Add random floating animation to the sail (the circle)
    const sail = document.querySelector('.sketchy-circle');
    if (sail) {
        let yOffset = 0;
        let direction = 1;
        setInterval(() => {
            yOffset += 0.5 * direction;
            if (yOffset > 5 || yOffset < -5) {
                direction *= -1;
            }
            sail.style.transform = `translateY(${yOffset}px)`;
        }, 100);
    }
});
