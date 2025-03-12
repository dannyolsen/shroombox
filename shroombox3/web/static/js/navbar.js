// Set the active navigation link based on the current page
document.addEventListener('DOMContentLoaded', function() {
    // Get the current page path
    const currentPath = window.location.pathname;
    
    // Map of paths to their corresponding navbar link classes
    const pathToClass = {
        '/': 'navbar-link-home',
        '/index': 'navbar-link-home',
        '/env-settings': 'navbar-link-env',
        '/settings': 'navbar-link-settings',
        '/logging': 'navbar-link-logging'
    };
    
    // Find the matching link class for the current path
    let activeClass = null;
    for (const [path, className] of Object.entries(pathToClass)) {
        if (currentPath === path || currentPath.startsWith(path + '/')) {
            activeClass = className;
            break;
        }
    }
    
    // If we found a matching class, add the active class to the corresponding link
    if (activeClass) {
        const activeLink = document.querySelector(`.${activeClass}`);
        if (activeLink) {
            activeLink.classList.add('navbar-link-active');
        }
    }
    
    console.log('Navigation initialized, active page:', currentPath);
}); 