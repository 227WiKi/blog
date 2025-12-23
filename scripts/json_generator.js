hexo.extend.generator.register('json_api', function (locals) {
    const config = hexo.config;
    const posts = [];

    const members = [
        "天城サリー", "河瀬詩", "麻丘真央", "西條和", "涼花萌",
        "相川奈央", "椎名桜月", "四条月", "月城咲舞", "望月りの",
        "折本美玲", "北原実咲", "黒崎ありす", "橘茉奈",
        "桧山依子", "三雲遥加", "南伊織", "吉沢珠璃"
    ];

    const rawPosts = locals.posts.sort('date', -1).limit(4);

    rawPosts.forEach(function (post) {
        let author = "22/7";

        if (post.tags && post.tags.length > 0) {
            post.tags.forEach(function (tag) {
                if (members.includes(tag.name)) {
                    author = tag.name;
                }
            });
        }

        let coverUrl = "";
        if (post.cover) {
            coverUrl = post.cover.match(/^http/) ? post.cover : (config.url + config.root + post.cover).replace(/([^:]\/)\/+/g, "$1");
        }

        let permalink = post.permalink;

        posts.push({
            title: post.title,
            date: post.date.format('YYYY.MM.DD'),
            link: permalink,
            cover: coverUrl,
            author: author
        });
    });

    return {
        path: 'api/posts.json',
        data: JSON.stringify(posts)
    };
});