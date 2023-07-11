#!/Applications/GIMP-2.10.app/Contents/MacOS/python
import array
import math

from gimpfu import *
import gimp , gimpplugin
pdb = gimp.pdb
import gtk, gimpui, gimpcolor
from gimpshelf import shelf


class ShiftColorChannelPlugin(gimpplugin.plugin):

	shelfkey = "color_shift_plugin"
	rValue = 0
	gValue = 0
	bValue = 0
	hueValue = 0
	saturationValue = 0
	brightnessValue = 0
	def query(self):
		gimp.install_procedure(
            "shiftColorsMain",
            "Shifts color channels.",
            "Shifts color channels by a given value",
            "Andrey Cherkasov",
            "Andrey Cherkasov",
            "2016",
            "<Image>/_Xtns/Shift colors",
            "RGB*",
            PLUGIN,
            [
                #next three parameters are common for all scripts that are inherited from gimpplugin.plugin
                (PDB_INT32, "run_mode", "Run mode"),
                (PDB_IMAGE, "image", "Input image"),
                (PDB_DRAWABLE, "drawable", "Input drawable"),
                #plugin specific parameters
                (PDB_INT32, "RLevel", "Red level"),
				(PDB_INT32, "GLevel", "Green level"),
				(PDB_INT32, "BLevel", "Blue level"),
				(PDB_INT32, "Saturation", "Saturation level"),
				(PDB_INT32, "Brightness", "Brightness level"),
				(PDB_INT32, "Hue", "Hue level")
            ],
            []
        )

	def start (self):
		gimp.main(self.init, self.quit, self.query, self._run)
	
	def init (self):
		pass

	def quit(self):
		pass

	def shelfStore (self, r, g, b, sat, brightness, hue ):
		shelf[self.shelfkey] = {
            "red":r,
            "green":g,
			"blue":b,
			"saturation":sat,
			"brightness":brightness,
			"hue":hue	
        }
	def clamp( self, val, lo, hi ):
		if val < lo:
			return lo
		elif val > hi:
			return hi
		return val
		
	def shiftColors (self):

		# get info from drawable
		(bx1, by1, bx2, by2) = self.drawable.mask_bounds
		bpp = self.drawable.bpp
		bw = bx2 - bx1
		bh = by2 - by1
		(ox, oy) = self.drawable.offsets

		# check if drawable valid
		if bw == 0 or bh == 0:
			gimp.message("Bad selection. Probably your selection is out of bounce of current layer")
			gimp.quit() 
		
		# bind to input
		src_rgn = self.drawable.get_pixel_rgn(bx1, by1, bw, bh, False, False)
		src_pixels = array.array("B", src_rgn[bx1:bx2, by1:by2])
		
		# create output
		layer = gimp.Layer(self.image, "Color shift", bw, bh, RGBA_IMAGE, 100, fill_mode=TRANSPARENT_FILL)
		layer.set_offsets(bx1 + ox, by1 + oy)
		self.image.add_layer(layer, 0)
		dest_bpp = 4 # always RGBA
		dst_rgn = layer.get_pixel_rgn(0, 0, bw, bh, True, True)
		dst_pixels = array.array("B", dst_rgn[0:bw, 0:bh])
		# Filtering
		gimp.progress_init('Shifting channels')
		for y in range(0, bh):
			for x in range(0, bw):

				pos = (y*bw + x) * bpp
				data = src_pixels[pos:(pos+bpp)]
				
				# first shift RGB channels then use clamp not to overflow
				data[0] = self.clamp ( data[0] + int(self.rValue), 0, 255 )
				data[1] = self.clamp ( data[1] + int(self.gValue), 0 ,255 )
				data[2] = self.clamp ( data[2] + int(self.bValue), 0, 255 )

				# then HSV filtering. Fill alpha with max value if there is no alpha
				data_hsv = gimpcolor.RGB(data[0],data[1],data[2],data[3] if bpp == 4 else 255)
				data_hsv = data_hsv.to_hsv()
				# Hue can overflow 
				data_hsv.h = data_hsv.h + self.hueValue 
				if data_hsv.h > 1.0:
					data_hsv.h -= 1.0
				if data_hsv.h < 0: 
					data_hsv.h += 1
				# Saturation and value is in range 0-1, so just clamp, no overflow
				data_hsv.s = self.clamp (data_hsv.s + self.saturationValue, 0.0, 1.0)
				data_hsv.v = self.clamp (data_hsv.v + self.brightnessValue, 0.0, 1.0 )
				data = data_hsv.to_rgb()
				# Updated data is always RGBA
				data_array = array.array( "B", data[0:dest_bpp] )
				dest_pos = (y * bw + x ) * dest_bpp
				# write result pixels to destinations
				dst_pixels[dest_pos:(dest_pos+dest_bpp)] = data_array 
			gimp.progress_update(float(y+1)/bh)
		dst_rgn[0:bw, 0:bh] = dst_pixels.tostring()
		layer.flush()
		layer.merge_shadow(True)
		layer.update(0,0,bw,bh)
		gimp.displays_flush()
	def shiftColorsMain(self, run_mode, image, drawable, RLevel = 0, GLevel = 0, BLevel = 0, Saturation = 0, Brightness = 0, Hue = 0):

		self.image = image 
		self.drawable = drawable

		#create settings if doesn't exist storage
		if not shelf.has_key(self.shelfkey):
			self.shelfStore(RLevel, GLevel, BLevel, Saturation, Brightness, Hue )
		self.create_dialog()
		
		# if threre is editor => run UI, otherwise run shifting
		if run_mode == RUN_INTERACTIVE:
			self.dialog.run()
		else:
			self.shiftColors()

	def create_dialog(self):
		self.dialog = gimpui.Dialog("Color shift", "Color shift dialog")
		#7x2 non-homogenous table
		self.table = gtk.Table(7, 2, False)
		self.table.set_row_spacings(8)
		self.table.set_col_spacings(8)
		self.table.show()


		# Red channel label
		self.redLabel = gtk.Label("Red value: ")
		self.redLabel.set_alignment(0.5, 0.5)
		self.redLabel.show()
		self.table.attach(self.redLabel, 0, 1, 0, 1)

		# Red channel spin button
		redAdjustment = gtk.Adjustment(0, -255, 255, 1)
		self.redButton = gtk.SpinButton(redAdjustment, 1)
		self.redButton.set_value(shelf[self.shelfkey]["red"])
		self.redButton.show()
		self.redButton.connect ("value-changed", self.updateRedValue )
		self.table.attach(self.redButton, 1, 2, 0, 1)

		# Green channel label
		self.greenLabel = gtk.Label("Green value: ")
		self.greenLabel.set_alignment(0.5, 0.5)
		self.greenLabel.show()
		self.table.attach(self.greenLabel, 0, 1, 1, 2)

		# Green channel spin button
		greenAdjustment = gtk.Adjustment(0, -255, 255, 1)
		self.greenButton = gtk.SpinButton(greenAdjustment, 1)
		self.greenButton.set_value(shelf[self.shelfkey]["green"])
		self.greenButton.show()
		self.greenButton.connect ("value-changed", self.updateGreenValue )
		self.table.attach(self.greenButton, 1, 2, 1, 2)
		
		# Blue channel label
		self.blueLabel = gtk.Label("Blue value: ")
		self.blueLabel.set_alignment(0.5, 0.5)
		self.blueLabel.show()
		self.table.attach(self.blueLabel, 0, 1, 2, 3)

		# Blue channel spin button
		blueAdjustment = gtk.Adjustment(0, -255, 255, 1)
		self.blueButton = gtk.SpinButton(blueAdjustment, 1)
		self.blueButton.set_value(shelf[self.shelfkey]["blue"])
		self.blueButton.show()
		self.blueButton.connect ("value-changed", self.updateBlueValue )
		self.table.attach(self.blueButton, 1, 2, 2, 3)

		# Saturation label
		self.saturationLabel = gtk.Label("Saturation value: ")
		self.saturationLabel.set_alignment(0.5, 0.5)
		self.saturationLabel.show()
		self.table.attach(self.saturationLabel, 0, 1, 3, 4)

		# Saturation spin button
		saturationAdjustment = gtk.Adjustment(0, -100, 100, 1)
		self.saturationButton = gtk.SpinButton(saturationAdjustment, 1)
		self.saturationButton.set_value(shelf[self.shelfkey]["saturation"])
		self.saturationButton.show()
		self.saturationButton.connect ("value-changed", self.updateSaturationValue )
		self.table.attach(self.saturationButton, 1, 2, 3, 4)

		# Brightness label
		self.brightnessLabel = gtk.Label("Brigthness value: ")
		self.brightnessLabel.set_alignment(0.5, 0.5)
		self.brightnessLabel.show()
		self.table.attach(self.brightnessLabel, 0, 1, 4, 5)

		# Brightness spin button
		brigthnessAdjustment = gtk.Adjustment(0, -100, 100, 1)
		self.brigthnessButton = gtk.SpinButton(brigthnessAdjustment, 1)
		self.brigthnessButton.set_value(shelf[self.shelfkey]["brightness"])
		self.brigthnessButton.show()
		self.brigthnessButton.connect ("value-changed", self.updateBrightnessValue )
		self.table.attach(self.brigthnessButton, 1, 2, 4, 5)

		# Hue label
		self.hueLabel = gtk.Label("Hue value: ")
		self.hueLabel.set_alignment(0.5, 0.5)
		self.hueLabel.show()
		self.table.attach(self.hueLabel, 0, 1, 5, 6)

		# Hue spin button
		hueAdjustment = gtk.Adjustment(0, -360, 360, 1)
		self.hueButton = gtk.SpinButton(hueAdjustment, 1)
		self.hueButton.set_value(shelf[self.shelfkey]["hue"])
		self.hueButton.show()
		self.hueButton.connect ("value-changed", self.updateHueValue )
		self.table.attach(self.hueButton, 1, 2, 5, 6)


		# Cancel button
		self.cancelButton = gtk.Button("Cancel")
		self.cancelButton.show()
		self.cancelButton.connect("clicked", self.onCancelClicked)
		self.table.attach(self.cancelButton, 1, 2, 6, 7)

		# Ok button
		self.okButton = gtk.Button("Ok")
		self.okButton.show()
		self.okButton.connect("clicked", self.onOkClicked)
		self.table.attach(self.okButton, 0, 1, 6, 7)


		#dialog inner frames
		#there is a table inside a hbox inside a vbox
		self.dialog.vbox.hbox1 = gtk.HBox(False, 7)
		self.dialog.vbox.hbox1.show()
		self.dialog.vbox.pack_start(self.dialog.vbox.hbox1, True, True, 7)
		self.dialog.vbox.hbox1.pack_start(self.table, True, True, 7)

	def onCancelClicked (self, widget ):
		gimp.quit()

	def onOkClicked ( self, widget ):
		# Store values and start shiftring
		self.shelfStore(self.redButton.get_value(), 
						 self.greenButton.get_value(),
						 self.blueButton.get_value(),
						 self.saturationButton.get_value(),
						 self.brigthnessButton.get_value(),
						 self.hueButton.get_value())
		self.shiftColors()
		gimp.quit()


	def updateRedValue ( self, widget  ): 
		self.rValue = self.redButton.get_value()


	def updateGreenValue ( self, widget  ): 
		self.gValue = self.greenButton.get_value()


	def updateBlueValue ( self, widget  ): 
		self.bValue = self.blueButton.get_value()

	def updateSaturationValue ( self, widget ):
		# In GIMP saturation value is in range 0-1. My plugin maps delta change from (-100, 100 ) to (-1, 1)
		self.saturationValue = self.saturationButton.get_value() / 100

	def updateBrightnessValue ( self, widget ):
		# In GIMP brightness value is in range 0-1. My plugin maps delta change from (-100, 100 ) to (-1, 1)
		self.brightnessValue = self.brigthnessButton.get_value() / 100
	
	def updateHueValue ( self, widget ):
		# In GIMP hue value is in range 0-1. My plugin maps delta change from (-360, 360 ) to (-1, 1)
		self.hueValue = self.hueButton.get_value() / 360



 
if __name__ == '__main__':
	ShiftColorChannelPlugin().start()

