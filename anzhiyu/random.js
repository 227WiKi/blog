var posts=["2025/12/17/934d855c134e88e111969e9ff08cc915/","2025/12/16/e44f3509e285b6b5c5dd9ff4eaa94351/"];function toRandomPost(){
    pjax.loadUrl('/'+posts[Math.floor(Math.random() * posts.length)]);
  };