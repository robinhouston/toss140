<div class="articlebox">
	{% ifchanged article.date %}
		<div class="date"><a href="/date/{{article.date}}{{q}}">{{article.date|date:"D jS F Y"}}</a></div>
	{% endifchanged %}
	{% for tweet in article.tweets %}
		{% include "tweet.inc" %}
	{% endfor %}
	<div class="author">
		– {%if article.author%}
				<a href="/author/{{article.author|urlencode}}{{q}}">{{article.author}}</a>,
			{%else%}
				author unknown,
			{%endif%}
		<a href="/organ/{{article.parent.name|urlencode}}{{q}}">{{article.parent.name}}</a>
		<a href="{{article.url|escape}}"><img src="/Icon_External_Link.png" /></a>
		{%if admin%}
			<a class="admin" href="/admin/datastore/edit?key={{article.key}}&amp;kind=Article&amp;next={{this_page|urlencode}}">e</a>
		{%endif%}
	</div>
</div>
