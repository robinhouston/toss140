{% if tweet.long_url and not tweet.is_retweet %}
	<div class="tweetbox">
		<div class="tweet">{{tweet.text|escape}}{%if admin%}
			<a class="admin" href="/admin/datastore/edit?key={{tweet.key}}&amp;kind=Tweet&amp;next={{this_page|urlencode}}">e</a>{%endif%}</div>
		<div class="meta">
			–&nbsp;
			{%if tweet.article.author%}<a href="/author/{{tweet.article.author|urlencode}}">{{tweet.article.author}}</a>, {%else%}from {%endif%}
			<a href="/organ/{{tweet.article.parent.name|urlencode}}">{{tweet.article.parent.name}}{%if tweet.article.date%}, {{tweet.article.date|date:"D jS F Y"}}{%endif%}
			<a href="{{tweet.long_url}}"><img src="/Icon_External_Link.png" /></a>
			<div class="tweeter"><a href="http://twitter.com/{{tweet.from_user}}/status/{{tweet.id}}">{{tweet.from_user}}</a></div>
			{%if admin%}<a class="admin" href="/admin/datastore/edit?key={{tweet.article.key}}&amp;kind=Article&amp;next={{this_page|urlencode}}">e</a>
			<a class="admin" href="/do/index-tweet?key={{tweet.key}}">r</a>{%endif%}
		</div>
	</div>
{% endif %}
