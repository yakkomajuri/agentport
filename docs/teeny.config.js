module.exports = {
    plugins: [
        require('./plugins/sidebar-plugin')(),
        require('./plugins/toc-plugin')({
            minHeadings: 3,
            title: 'On this page',
        }),
    ],
}
