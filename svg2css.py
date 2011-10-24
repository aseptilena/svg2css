#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import svg
import re
import math
import os.path
from optparse import OptionParser

class CSSStyle(dict):
	def __str__(self):
		s = ""
		for name,style in self.iteritems():
			if name=="transform":
				s += CSSStyle.__transform(style)
				continue
			if isinstance(style, list):
				s += "".join(["%s:%s;" % (name, s) for s in style])
				continue
			if not isinstance(style, str):
				style = str(style)
			s += "%s:%s;" % (name, style)
		return s
	
	@classmethod
	def __transform(cls, transform):
		style = str(transform)
		s = ""
		for name in ["transform", "-ms-transform", "-o-transform", "-webkit-transform"]:
			s += "%s:%s;" % (name, style)
		if isinstance(transform, str) or isinstance(transform, unicode):
			s += "-moz-transform:%s;" % transform
		else:
			s += "-moz-transform:%s;" % transform.toStringMoz()
		return s
	
	__re_fill_url = re.compile("url\(#(.*)\)")
	def addFill(self, element):
		svgstyle = element.style
		if "fill" not in svgstyle or svgstyle["fill"] == "none":
			return
			
		try:
			fill = svgstyle["fill"]
			m = CSSStyle.__re_fill_url.match(fill)
			if m:
				fill = element.root.getElementById(m.group(1))
				if isinstance(fill, svg.LinearGradient):
					self.__addLinearGradient(element, fill)
				elif isinstance(fill, svg.RadialGradient):
					self.__addRadialGradient(element, fill)
				return
			color = svg.Color(fill)
			if "fill-opacity" in svgstyle:
				color.a = float(svgstyle["fill-opacity"])
			self["background-color"] = color
		except Exception,e:
			print svgstyle["fill"], e
	
	def __addLinearGradient(self, element, fill):
		root = fill.root
		stops = fill
		while len(stops)==0 and stops.href:
			stops = root.getElementById(stops.href[1:])
		background = []
		
		#座標補正
		point1 = svg.Point(fill.x1, fill.y1)
		point2 = svg.Point(fill.x2, fill.y2)
		point1 = fill.gradientTransform.toMatrix() * point1
		point2 = fill.gradientTransform.toMatrix() * point2
		if fill.gradientUnits == "userSpaceOnUse":
			stroke = svg.Length(element.style.get("stroke-width",0))
			point1 = svg.Point(
				point1.x - svg.Length(self["left"]) - stroke,
				point1.y - svg.Length(self["top"]) - stroke)
			point2 = svg.Point(
				point2.x - svg.Length(self["left"]) - stroke,
				point2.y - svg.Length(self["top"]) - stroke)

		def svgOffsetToPoint(offset):
			return point1*(1-offset) + point2*offset
		
		#css3のデフォルト
		rad = -math.atan2(point2.y-point1.y, point2.x-point1.x)
		vec = svg.Point(math.cos(rad), -math.sin(rad))
		deg = rad/math.pi*180
		width = svg.Length(self["width"])
		height = svg.Length(self["height"])
		point0 = svg.Point(0,0)
		if 0<deg<90:
			point0 = svg.Point(0, height)
		elif 90<=deg:
			point0 = svg.Point(width, height)
		elif deg<-90:
			point0 = svg.Point(width, 0)
		gradientlen = (svg.Point(width, height)-point0*2) * vec

		def pointToCSSOffset(point):
			offset = (point - point0) * vec / gradientlen
			return offset
		
		def svgOffsetToCSSOffset(offset):
			return pointToCSSOffset(svgOffsetToPoint(offset))

		gradient = "(%.1fdeg" % deg
		color_stops = []
		for stop in stops:
			color = svg.Color(stop.style["stop-color"])
			if float(stop.style.get("stop-opacity", "1"))<=0.999:
				color.a = float(stop.style.get("stop-opacity", "1"))
			gradient += ",%s %.1f%%" % (color, svgOffsetToCSSOffset(stop.offset)*100)
			
		gradient += ")"
		background.append("linear-gradient" + gradient)
		background.append("-o-linear-gradient" + gradient)
		background.append("-moz-linear-gradient" + gradient)
		background.append("-ms-linear-gradient" + gradient)
		background.append("-webkit-linear-gradient" + gradient)
		
		#webkit
		webkit = "-webkit-gradient(linear,%f %f,%f %f," % (point1.x.px, point1.y.px, point2.x.px, point2.y.px)
		color = svg.Color(stops[0].style["stop-color"])
		if float(stops[0].style.get("stop-opacity", "1"))<=0.999:
			color.a = float(stops[0].style.get("stop-opacity", "1"))
		webkit += "from(%s)," % color
		if len(stops)>2:
			for stop in stops[1:-1]:
				color = svg.Color(stop.style["stop-color"])
				if float(stop.style.get("stop-opacity", "1"))<=0.999:
					color.a = float(stop.style.get("stop-opacity", "1"))
				webkit += "color-stop(%f,%s)," % (stop.offset, color)
		color = svg.Color(stops[-1].style["stop-color"])
		if float(stops[-1].style.get("stop-opacity", "1"))<=0.999:
			color.a = float(stops[-1].style.get("stop-opacity", "1"))
		webkit += "to(%s))" % color
		background.append(webkit)

		self["background"] = background
		
	def __addRadialGradient(self, element, fill):
		root = fill.root
		stops = fill
		while len(stops)==0 and stops.href:
			stops = root.getElementById(stops.href[1:])
		background = []
		
		#座標補正
		gradientTransform = fill.gradientTransform.toMatrix()
		center = svg.Point(fill.cx, fill.cy)
		finish = svg.Point(fill.fx, fill.fy)
		center = gradientTransform * center
		finish = gradientTransform * finish
		
		if fill.gradientUnits == "userSpaceOnUse":
			stroke = svg.Length(element.style.get("stroke-width",0))
			center = svg.Point(
				center.x - svg.Length(self["left"]) - stroke,
				center.y - svg.Length(self["top"]) - stroke)
			finish = svg.Point(
				finish.x - svg.Length(self["left"]) - stroke,
				finish.y - svg.Length(self["top"]) - stroke)
		
		#半径の決定
		zero = svg.Length("0")
		point0 = gradientTransform * svg.Point(zero, zero)
		rx = svg.Length(abs(gradientTransform * svg.Point(fill.r, zero) - point0), "px")
		ry = svg.Length(abs(gradientTransform * svg.Point(zero, fill.r) - point0), "px")
		r = fill.r
		
		gradient = ""
		for stop in stops:
			color = svg.Color(stop.style["stop-color"])
			if float(stop.style.get("stop-opacity", "1"))<=0.999:
				color.a = float(stop.style.get("stop-opacity", "1"))
			gradient += ",%s %.1f%%" % (color, stop.offset*100)
		background.append("radial-gradient(%s %s,%s %s%s)" % (center.x, center.y, rx, ry, gradient))
		background.append("-o-radial-gradient(%s %s,%s %s%s)" % (center.x, center.y, rx, ry, gradient))
		background.append("-moz-radial-gradient(%s %s,circle%s)" % (center.x, center.y, gradient))
		background.append("-moz-radial-gradient(%s %s,%s %s%s)" % (center.x, center.y, rx, ry, gradient))
		background.append("-ms-radial-gradient(%s %s,%s %s%s)" % (center.x, center.y, rx, ry, gradient))
		background.append("-webkit-radial-gradient(%s %s,%s %s%s)" % (center.x, center.y, rx, ry, gradient))

		self["background"] = background
		
class CSSWriter(svg.SVGHandler):
	def __init__(self, name, html = None, css = None):
		self.__name = name
		self._html = html or open(name + ".html", "w")
		self._css = css or open(name + ".css", "w")
		self.__id = 0
		self._css_classes = set()
		self.__clipnames = {}
		
	def newName(self, x=None):
		if x and isinstance(x, svg.Element) and x.id:
			return "svg" + x.id
		self.__id = self.__id + 1
		return "id%04d" % self.__id
		
	def svg(self, x):
		self._html.write("""<!DOCTYPE html> 
<head> 
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="content-script-type" content="text/javascript" /> 
<meta http-equiv="content-style-type" content="text/css" /> 
<link rel="stylesheet" href="./%s.css">
<title>%s</title>
</head>
<body>
<div class="svg">\n""" % (self.__name, self.__name))
		self._css.write('@charset "utf-8";\n')
		self._css.write(".svg{top:0px;left:0px;width:%s;height:%s;position:absolute;}\n" % (str(x.width), str(x.height)))
		svg.SVGHandler.svg(self, x)
		self._html.write("""</div>\n</body></html>\n""")
		
	def rect(self, x):
		name = self.newName(x)
		if name not in self._css_classes:
			self._css_classes.add(name)
			css = CSSStyle()
			stroke = svg.Length(0)
			
			#クリップパスの設定
			self.__clipPath(name, x)
			
			#ストロークの描画
			if "stroke" in x.style and x.style["stroke"] != 'none':
				try:
					stroke = svg.Length(x.style.get("stroke-width",0))
					css["border-width"] = stroke
					css["border-style"] = "solid"
					color = svg.Color(x.style["stroke"])
					if "stroke-opacity" in x.style:
						color.a = float(x.style["stroke-opacity"])
					css["border-color"] = color
				except:
					pass
			
			#位置と大きさの設定
			css["position"] = "absolute"
			css["left"] = x.x - stroke/2
			css["top"] = x.y - stroke/2
			css["width"] = x.width - stroke
			css["height"] = x.height - stroke
			
			#角を丸める
			if x.rx and x.ry:
				css["border-radius"] = "%s/%s" % (str(x.rx+stroke/2), str(x.ry+stroke/2))
			elif x.rx:
				css["border-radius"] = x.rx+stroke/2
			elif x.ry:
				css["border-radius"] = x.ry+stroke/2
		
			#変形
			if x.transform:
				#CSSとSVGの原点の違いを補正
				transform = x.transform.toMatrix()
				transform = transform * svg.Transform.Translate(x.x+x.width/2, x.y+x.height/2)
				transform = svg.Transform.Translate(-x.x-x.width/2, -x.y-x.height/2) * transform
				css["transform"] = transform

			#フィルを指定する
			css.addFill(x)
				
			#出力
			self._css.write(".%s{%s}\n" % (name, str(css)))
		
		#クリップの設定
		if name in self.__clipnames:
			clipname = self.__clipnames[name]
			self._html.write('<div class="%s"><div class="%sinverse"><div class="%s"></div></div></div>\n' % (clipname, clipname, name))
			return
		
		self._html.write('<div class="%s"></div>\n' % name)
	
	def arc(self, x):
		name = self.newName(x)
		if name not in self._css_classes:
			self._css_classes.add(name)
			css = CSSStyle()
			stroke = svg.Length(0)
			
			#クリップパスの設定
			self.__clipPath(name, x)
			
			#ストロークの描画
			if "stroke" in x.style and x.style["stroke"] != 'none':
				try:
					stroke = svg.Length(x.style.get("stroke-width",1))
					css["border-width"] = stroke
					css["border-style"] = "solid"
					color = svg.Color(x.style["stroke"])
					if "stroke-opacity" in x.style:
						color.a = float(x.style["stroke-opacity"])
					css["border-color"] = color
				except:
					pass
					
			#位置と大きさの設定
			css["position"] = "absolute"
			css["left"] = str(x.cx - x.rx - stroke/2)
			css["top"] = str(x.cy - x.ry - stroke/2)
			css["width"] = str(x.rx * 2 - stroke)
			css["height"] = str(x.ry * 2 - stroke)
			
			#角を丸める
			css["border-radius"] = "%s/%s" % (str(x.rx+stroke/2), str(x.ry+stroke/2))
		
			#フィルを指定する
			css.addFill(x)
			
			#変形
			if x.transform:
				#CSSとSVGの原点の違いを補正
				transform = x.transform.toMatrix()
				transform = transform * svg.Transform.Translate(x.cx, x.cy)
				transform = svg.Transform.Translate(-x.cx, -x.cy) * transform
				css["transform"] = transform
			
			#出力
			self._css.write(".%s{%s}\n" % (name, str(css)));

		#クリップの設定
		if name in self.__clipnames:
			clipname = self.__clipnames[name]
			self._html.write('<div class="%s"><div class="%sinverse"><div class="%s"></div></div></div>\n' % (clipname, clipname, name))
			return

		self._html.write('<div class="%s"></div>\n' % name);
	
	def group(self, x):
		name = self.newName(x)
		if name not in self._css_classes:
			self._css_classes.add(name)
			css = CSSStyle()

			#クリップパスの設定
			self.__clipPath(name, x)

			css["position"] = "absolute"
			css["margin"] = "0px"
			
			#変形
			if x.transform:
				transform = x.transform.toMatrix()
				css["transform"] = transform
			
			#出力
			self._css.write(".%s{%s}\n" % (name, str(css)));

		if name in self.__clipnames:
			clipname = self.__clipnames[name]
			self._html.write('<div class="%s"><div class="%sinverse">\n' % (clipname, clipname))

		self._html.write('<div class="%s">\n' % name)
		svg.SVGHandler.group(self, x)
		self._html.write('</div>\n');

		if name in self.__clipnames:
			clipname = self.__clipnames[name]
			self._html.write('</div></div>\n')

		
	def use(self, x):
		name = self.newName(x)
		css = CSSStyle()
		css["position"] = "absolute"
		css["margin"] = "0px"

		css["left"] = str(-x.width/2)
		css["top"] = str(-x.height/2)
		css["width"] = str(x.width)
		css["height"] = str(x.height)
		
		transform = svg.Transform.Translate(x.x, x.y)
		if x.transform:
			transform = x.transform.toMatrix() * transform
		transform = svg.Transform.Translate(x.width/2, x.height/2) * transform
		css["transform"] = transform

		self._css.write(".%s{%s}\n" % (name, str(css)));
		self._html.write('<div class="%s">\n' % name)
		svg.SVGHandler.use(self, x)
		self._html.write('</div>\n');
	
	def __clipPath(self, element_name, element):
		#クリップパスが設定されているか確認
		if not element.clip_path:
			return
		m = re.match("^url\(#(.*)\)$", element.clip_path)
		if not m:
			return
		
		#クリップパスオブジェクトを取得
		x = element.root.getElementById(m.group(1))
				
		name = self.newName()

		css = CSSStyle()
		invtransform = svg.Transform("")
		if isinstance(x[0], svg.Rect):
			css["position"] = "absolute"
			css["left"] = x[0].x
			css["top"] = x[0].y
			css["width"] = x[0].width
			css["height"] = x[0].height
			if x[0].rx and x[0].ry:
				css["border-radius"] = "%s/%s" % (str(x[0].rx), str(x[0].ry))
			elif x[0].rx:
				css["border-radius"] = x[0].rx
			elif x[0].ry:
				css["border-radius"] = x[0].ry
			
			#座標変換
			if x[0].transform or element.transform:
				#CSSとSVGの原点の違いを補正
				transform = element.transform.toMatrix() * x[0].transform.toMatrix()
				invtransform.append(transform.inverse())
				transform = transform * svg.Transform.Translate(x[0].x+x[0].width/2, x[0].y+x[0].height/2)
				transform = svg.Transform.Translate(-x[0].x-x[0].width/2, -x[0].y-x[0].height/2) * transform
				css["transform"] = transform
			invtransform.append(svg.Transform.Translate(-x[0].x, -x[0].y))

			css["overflow"] = "hidden"
		self._css.write(".%s{%s}\n" % (name, str(css)));
		
		css = CSSStyle()
		css["position"] = "absolute"
		css["transform"] = invtransform.toMatrix()
		self._css.write(".%sinverse{%s}\n" % (name, str(css)));
		self.__clipnames[element_name] = name
		
		return name
		
	def __del__(self):
		self._html.close()
		self._css.close()

class SlideWriter(CSSWriter):
	slide_prefix = "slide"
	container_prefix = "container"

	#スライドの枚数を数えるクラス
	class CountSlide(svg.SVGHandler):
		def __init__(self, html, css):
			self.__slides = 0
			self._html = html
			self._css = css
		
		def group(self, x):
			if x.groupmode!="layer":
				return
			self.__slides += 1
			name = SlideWriter.slide_prefix + str(self.__slides)
			
			css = CSSStyle()
			css["transform"] = "translateX(-%d%%)" % (self.__slides * 100)
			self._css.write("#%s:target .%s {%s}\n" % (name, SlideWriter.container_prefix, str(css)));
			self._css.write("#%s{left:%d%%}\n" % (SlideWriter.container_prefix + str(self.__slides), self.__slides*100))
			self._html.write('<div id="%s">' % name)
		
		@property
		def slides(self):
			return self.__slides
		
		def printEndTags(self):
			self._html.write("</div>" * self.__slides + "\n")
	
	def __init__(self, name, html = None, css = None):
		CSSWriter.__init__(self, name, html, css)
		self.__name = name
		self.__slides = 0
		self.__all_slides = 0
		self.__width = 0
		self.__height = 0
		
	def svg(self, x):
		self._html.write("""<!DOCTYPE html> 
<head> 
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta http-equiv="content-script-type" content="text/javascript" /> 
<meta http-equiv="content-style-type" content="text/css" /> 
<link rel="stylesheet" href="./%s.css">
<title>Slide: %s</title>
</head>
<body>
<div class="svg">""" % (self.__name, self.__name))
		self._css.write('@charset "utf-8";\n')
		
		#サイズ設定
		self._css.write(".svg{top:0px;left:0px;width:100%;height:100%;position:absolute;overflow: hidden;}\n" )
		self.__width = x.width
		self.__height = x.height
		self._css.write(""".%s {
position: absolute; 
width: 100%%; 
height: 100%%; }\n""" % SlideWriter.container_prefix)
		
		#アニメーションの設定
		self._css.write(""".%s {
-ms-transition: -ms-transform 0.8s;
-webkit-transition: -webkit-transform 0.8s;
-moz-transition: -moz-transform 0.8s;
-o-transition: -o-transform 0.8s; }\n""" % SlideWriter.container_prefix)

		#初期位置の設定
		self._css.write(""".%s {
transform: translateX(-100%%);
-ms-transform: translateX(-100%%);
-webkit-transform: translateX(-100%%);
-moz-transform: translateX(-100%%);
-o-transform: translateX(-100%%);]
display: box;
display: -ms-box;
display: -webkit-box;
display: -moz-box;
display: -o-box;
box-align: center;
-ms-box-align: center;
-webkit-box-align: center;
-moz-box-align: center;
-o-box-align: center;
box-pack: center;
-ms-box-pack: center;
-webkit-box-pack: center;
-moz-box-pack: center;
-o-box-pack: center;
}\n""" % SlideWriter.container_prefix)

		#スライド移動ボタンの設定
		self._css.write(""".nextbutton, .backbutton {
position:absolute;
top:0px;
height:100%;
width:50%;
margin:0px;
padding:0px;}
.nextbutton {right: 0px}
.backbutton {left: 0px}
""")
		
		#スライドの開始タグを出力
		counter = SlideWriter.CountSlide(self._html, self._css)
		x.callHandler(counter)
		self.__all_slides = counter.slides
		
		#内容を出力
		svg.SVGHandler.svg(self, x)
		
		#スライドの終了タグを出力
		counter.printEndTags()
		self._html.write("""</div></body></html>\n""")

	def group(self, x):
		if x.groupmode!="layer":
			CSSWriter.group(self, x)
		else:
			self.__slides += 1
			name = SlideWriter.container_prefix + str(self.__slides)
			self._html.write('<div id="%s" class="%s">\n' % (name, SlideWriter.container_prefix))

			#スライドの内容を出力
			name = self.newName(x)
			css = CSSStyle()
			css["margin"] = "0px auto"
			css["width"] = self.__width
			css["height"] = self.__height
			css["position"] = "relative"
			css["overflow"] = "hidden"
			self._css.write(".%s{%s}\n" % (name, str(css)));
			self._html.write('<div class="%s">\n' % name)
			svg.SVGHandler.group(self, x)
			self._html.write('</div>\n')
			
			#移動ボタン
			backslide = self.__slides-1
			nextslide = self.__slides+1
			if backslide<=0:
				backslide = self.__all_slides
			if nextslide>self.__all_slides:
				nextslide = 1
			self._html.write('<a href="#slide%d" class="backbutton"></a>\n' % backslide)
			self._html.write('<a href="#slide%d" class="nextbutton"></a>\n' % nextslide)

			self._html.write('</div>\n')


def main():
	#オプション解析
	parser = OptionParser(usage = "usage: %prog [options] svgfile")
	parser.add_option("-s", "--slide", dest="slide",
		action="store_true", default=False, help="Make slides")
	(options, args) = parser.parse_args()
	if len(args)==0:
		parser.print_help()
		return
	
	#SVGファイル取得
	svgfile = open(args[0], "r")
	root, ext = os.path.splitext(args[0])
	name = os.path.basename(root)
	html = open(name + ".html", "w")
	css = open(name + ".css", "w")

	#解析＆変換
	p = svg.Parser()
	if options.slide:
		writer = SlideWriter(name, html, css)
	else:
		writer = CSSWriter(name, html, css)
	s = p.parse(svgfile)
	s.callHandler(writer)
	return

if __name__=="__main__":
	main()
